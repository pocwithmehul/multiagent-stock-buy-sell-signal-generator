"""
Feature flag service with automatic provider selection.

This module provides the main entry point for feature flag checks in the
Stock Signal application. It automatically selects the appropriate provider
based on the current environment:

    - Local (APP_ENV=local): Uses Unleash self-hosted server
    - AWS (APP_ENV=qa/stg/prod): Uses AWS AppConfig

Design Pattern: Facade Pattern
    The FeatureFlagService acts as a simplified interface to the underlying
    provider implementations. Callers don't need to know which provider
    is being used.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    Application Code                              │
    │                                                                  │
    │   from infrastructure.feature_flags import is_feature_enabled   │
    │   if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):       │
    │       run_watchlist_analysis()                                  │
    │                                                                  │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                  FeatureFlagService                              │
    │                 (This module - Facade)                           │
    │                                                                  │
    │   - Auto-selects provider based on APP_ENV                       │
    │   - Provides convenience functions                               │
    │   - Manages singleton instance                                   │
    │                                                                  │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │  is_aws_environment()?  │
                    └────────────┬────────────┘
                           │
              ┌────────────┴────────────┐
              │ False                   │ True
              ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  UnleashProvider │      │ AppConfigProvider│
    │    (local dev)   │      │   (AWS cloud)    │
    └──────────────────┘      └──────────────────┘

Usage:
    # Simple usage with convenience function
    from infrastructure.feature_flags import is_feature_enabled, FeatureFlag

    if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
        run_watchlist_analysis()

    # Advanced usage with service instance
    from infrastructure.feature_flags import get_feature_flag_service

    service = get_feature_flag_service()
    all_flags = service.get_all_flags()

References:
    - Facade Pattern: https://refactoring.guru/design-patterns/facade
    - Singleton Pattern: https://refactoring.guru/design-patterns/singleton
"""

from typing import Dict, Optional

# Import environment detection function
# This determines whether we're in local or AWS environment
from infrastructure.env_config import is_aws_environment

# Import from local modules
from .provider import FeatureFlagProvider
from .flags import FeatureFlag, FEATURE_FLAG_DEFAULTS


class FeatureFlagService:
    """
    Feature flag service that auto-selects the appropriate provider.

    This class is the primary interface for checking feature flags.
    It handles:
        - Automatic provider selection based on environment
        - Delegation to the underlying provider
        - Consistent default value handling

    Provider Selection Logic:
        - APP_ENV=local (or unset): Uses UnleashProvider
        - APP_ENV=qa/stg/prod: Uses AppConfigProvider

    Thread Safety:
        The service is thread-safe because the underlying providers
        handle thread safety. Multiple threads can safely call
        is_enabled() concurrently.

    Singleton Pattern:
        Use get_feature_flag_service() to get the global singleton
        instance. This ensures all code uses the same provider
        and shares the same cache.

    Attributes:
        _provider: The underlying FeatureFlagProvider instance

    Example:
        # Using the service directly
        service = FeatureFlagService()
        if service.is_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
            run_watchlist_analysis()

        # Using convenience functions (preferred)
        from infrastructure.feature_flags import is_feature_enabled
        if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
            run_watchlist_analysis()
    """

    def __init__(self, provider: FeatureFlagProvider = None):
        """
        Initialize the feature flag service.

        The service can be initialized with a specific provider for
        testing purposes, or it will auto-select based on environment.

        Args:
            provider: Optional provider override for testing.
                     If not provided, auto-selects based on APP_ENV.

        Example:
            # Auto-select provider (normal usage)
            service = FeatureFlagService()

            # Use specific provider (for testing)
            from unittest.mock import Mock
            mock_provider = Mock(spec=FeatureFlagProvider)
            mock_provider.is_enabled.return_value = True
            service = FeatureFlagService(provider=mock_provider)
        """
        # Store the provider instance
        self._provider = provider

        # If no provider given, auto-select based on environment
        if self._provider is None:
            self._provider = self._create_provider()

    def _create_provider(self) -> FeatureFlagProvider:
        """
        Create the appropriate provider based on environment.

        This method checks the APP_ENV environment variable to determine
        which provider to use:
            - local (default): UnleashProvider for local development
            - qa/stg/prod: AppConfigProvider for AWS environments

        Returns:
            FeatureFlagProvider: The appropriate provider instance

        Note:
            Imports are done inside the method to avoid circular imports
            and to defer loading until needed.
        """
        # Check if we're in an AWS environment (qa, stg, prod)
        if is_aws_environment():
            # Use AWS AppConfig for cloud environments
            from .appconfig_provider import AppConfigProvider
            return AppConfigProvider()
        else:
            # Use Unleash for local development
            from .unleash_provider import UnleashProvider
            return UnleashProvider()

    def is_enabled(
        self,
        flag: FeatureFlag,
        default: bool = None,
        context: Optional[Dict] = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        This is the main method for checking flag states. It delegates
        to the underlying provider.

        Args:
            flag: The FeatureFlag enum member to check.
                 Use the enum for type safety and IDE autocomplete.

            default: Override the default value for this flag.
                    If None, uses the value from FEATURE_FLAG_DEFAULTS.
                    Useful for testing or special cases.

            context: Optional context for targeting.
                    Supported keys depend on the provider:
                    - Unleash: user_id, session_id, custom properties
                    - AppConfig: Not used (accepted for compatibility)

        Returns:
            bool: True if the flag is enabled, False otherwise.

        Example:
            # Simple check
            if service.is_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
                run_watchlist_analysis()

            # With user targeting
            if service.is_enabled(
                FeatureFlag.PREMARKET_ANALYSIS,
                context={"user_id": "123"}
            ):
                show_premarket_ui()

            # With custom default
            if service.is_enabled(FeatureFlag.NEW_FEATURE, default=True):
                # Use new feature even if not in defaults
                pass
        """
        # ─────────────────────────────────────────────────────────────────────
        # Determine Default Value
        # ─────────────────────────────────────────────────────────────────────

        # If no default provided, look up from FEATURE_FLAG_DEFAULTS
        if default is None:
            default = FEATURE_FLAG_DEFAULTS.get(flag, False)

        # ─────────────────────────────────────────────────────────────────────
        # Delegate to Provider
        # ─────────────────────────────────────────────────────────────────────

        # Call the provider with the flag name (string) and context
        return self._provider.is_enabled(flag.value, default=default, context=context)

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.

        Useful for:
            - Debugging flag states
            - API endpoints that expose flag status
            - Dashboard displays

        Returns:
            Dict[str, bool]: Dictionary mapping flag names to their states.

        Example:
            >>> service.get_all_flags()
            {
                'single_stock_analysis': True,
                'watchlist_analysis': False,
                'premarket_analysis': False,
                'aftermarket_analysis': False
            }
        """
        return self._provider.get_all_flags()

    def refresh(self) -> None:
        """
        Refresh the feature flag cache.

        Forces the provider to fetch fresh configuration. Useful for:
            - After deploying new flag configurations
            - Before critical operations
            - Testing/debugging

        Note:
            This is usually not needed as providers refresh automatically.
        """
        self._provider.refresh()

    def close(self) -> None:
        """
        Clean up resources.

        Call this when shutting down the application to ensure
        clean release of resources (network connections, threads, etc.).
        """
        self._provider.close()


# ─────────────────────────────────────────────────────────────────────────────
# Singleton Instance Management
# ─────────────────────────────────────────────────────────────────────────────

# Global service instance (lazy-loaded)
# Using a module-level variable for simplicity
# Thread-safe because Python's GIL protects the assignment
_service: Optional[FeatureFlagService] = None


def get_feature_flag_service() -> FeatureFlagService:
    """
    Get the global FeatureFlagService singleton instance.

    This function ensures that all code in the application uses the
    same FeatureFlagService instance, which means:
        - Same provider instance (shared cache)
        - Consistent behavior across the app
        - Efficient resource usage

    The instance is created lazily on first call.

    Returns:
        FeatureFlagService: The global singleton instance

    Example:
        service = get_feature_flag_service()
        flags = service.get_all_flags()

    Thread Safety:
        This function is thread-safe. Multiple threads calling it
        simultaneously may create multiple instances briefly, but
        will converge on a single instance.
    """
    global _service

    # Lazy initialization
    if _service is None:
        _service = FeatureFlagService()

    return _service


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

def is_feature_enabled(
    flag: FeatureFlag,
    default: bool = None,
    context: Optional[Dict] = None,
) -> bool:
    """
    Convenience function to check if a feature flag is enabled.

    This is the recommended way to check feature flags. It uses the
    global singleton service instance.

    Usage:
        from infrastructure.feature_flags import is_feature_enabled, FeatureFlag

        # Simple check
        if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
            run_watchlist_analysis()

        # With user targeting (for gradual rollout)
        if is_feature_enabled(FeatureFlag.PREMARKET_ANALYSIS, context={"user_id": "123"}):
            run_premarket_analysis()

        # With custom default (override FEATURE_FLAG_DEFAULTS)
        if is_feature_enabled(FeatureFlag.NEW_FEATURE, default=True):
            try_new_feature()

    Args:
        flag: The FeatureFlag enum member to check.

        default: Override the default value for this flag.
                If None, uses FEATURE_FLAG_DEFAULTS.

        context: Optional targeting context.
                Keys: user_id, session_id, or custom properties.

    Returns:
        bool: True if the flag is enabled, False otherwise.

    Example with targeting:
        # Enable feature for specific user
        context = {"user_id": "beta_tester_123"}
        if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS, context=context):
            show_watchlist_ui()
    """
    return get_feature_flag_service().is_enabled(flag, default=default, context=context)


def get_all_flags() -> Dict[str, bool]:
    """
    Get all feature flags and their current values.

    Convenience function that uses the global singleton service.

    Returns:
        Dict[str, bool]: Dictionary mapping flag names to their states.

    Example:
        from infrastructure.feature_flags import get_all_flags

        flags = get_all_flags()
        print(f"Watchlist enabled: {flags['watchlist_analysis']}")

        # Or iterate
        for name, enabled in get_all_flags().items():
            print(f"{name}: {'ON' if enabled else 'OFF'}")
    """
    return get_feature_flag_service().get_all_flags()
