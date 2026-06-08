"""
Abstract feature flag provider interface.

This module defines the contract that all feature flag providers must implement.
It follows the Strategy Pattern, allowing the application to switch between
different feature flag backends (Unleash, AWS AppConfig, etc.) without
changing the calling code.

Design Pattern: Strategy Pattern
    - FeatureFlagProvider is the abstract strategy interface
    - UnleashProvider and AppConfigProvider are concrete strategies
    - FeatureFlagService is the context that uses these strategies

Architecture:
    ┌─────────────────────────────┐
    │  FeatureFlagProvider (ABC)  │  <-- This module
    └──────────────┬──────────────┘
                   │ implements
         ┌─────────┴─────────┐
         ▼                   ▼
    ┌──────────────┐  ┌──────────────────┐
    │UnleashProvider│  │AppConfigProvider │
    │  (local dev) │  │   (AWS cloud)    │
    └──────────────┘  └──────────────────┘

References:
    - Python ABC: https://docs.python.org/3/library/abc.html
    - Strategy Pattern: https://refactoring.guru/design-patterns/strategy
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class FeatureFlagProvider(ABC):
    """
    Abstract base class for feature flag providers.

    All feature flag providers (Unleash, AppConfig, etc.) must implement
    this interface to ensure consistent behavior across different backends.

    The provider is responsible for:
        1. Connecting to the feature flag service
        2. Caching flag values for performance
        3. Refreshing flags periodically
        4. Handling fallbacks when the service is unavailable

    Implementing a New Provider:
        1. Create a new class that inherits from FeatureFlagProvider
        2. Implement all @abstractmethod methods
        3. Override close() if cleanup is needed
        4. Add the provider to FeatureFlagService._create_provider()

    Thread Safety:
        Providers should be thread-safe as they may be accessed from
        multiple threads (e.g., web request handlers).

    Example Implementation:
        class MyProvider(FeatureFlagProvider):
            def is_enabled(self, flag_name, default=False, context=None):
                # Check flag in your backend
                return self._backend.check(flag_name) or default

            def get_all_flags(self):
                return {f.value: self.is_enabled(f) for f in FeatureFlag}

            def refresh(self):
                self._backend.sync()
    """

    @abstractmethod
    def is_enabled(
        self,
        flag_name: str,
        default: bool = False,
        context: Optional[Dict] = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        This is the primary method for checking flag status. It should:
            1. Check the cached value first for performance
            2. Fall back to the default if the flag is not found
            3. Handle errors gracefully by returning the default

        Args:
            flag_name: Name of the feature flag (e.g., "watchlist_analysis").
                      Should match the flag name in the provider's backend.

            default: Default value to return if:
                    - The flag doesn't exist in the backend
                    - The backend is unavailable
                    - An error occurs during the check

            context: Optional context for advanced targeting/segmentation.
                    Common context keys:
                    - user_id: For user-based rollouts (e.g., beta users)
                    - session_id: For session-based experiments
                    - environment: For environment-specific flags
                    - Custom properties for A/B testing

        Returns:
            bool: True if the flag is enabled for the given context,
                  False otherwise.

        Example:
            # Simple check
            if provider.is_enabled("new_feature"):
                use_new_feature()

            # With user targeting
            if provider.is_enabled("beta_feature", context={"user_id": "123"}):
                show_beta_ui()
        """
        pass

    @abstractmethod
    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.

        This method returns the current state of all known feature flags.
        Useful for:
            - Debugging flag states
            - Exposing flags via API endpoints
            - Dashboard displays

        Returns:
            Dict[str, bool]: Dictionary mapping flag names to their
                            boolean enabled/disabled state.

        Example:
            >>> provider.get_all_flags()
            {
                'single_stock_analysis': True,
                'watchlist_analysis': False,
                'premarket_analysis': False,
                'aftermarket_analysis': False
            }
        """
        pass

    @abstractmethod
    def refresh(self) -> None:
        """
        Refresh the feature flag cache from the source.

        This method forces a synchronous refresh of all flag values
        from the backend service. Use cases:
            - Manual refresh after deploying new flags
            - Ensuring latest values before critical operations
            - Recovery after network issues

        Most providers also refresh automatically in the background
        on a configurable interval.

        Note:
            This method should be idempotent and safe to call multiple times.
            It should handle errors gracefully without crashing.

        Example:
            # Force refresh before checking flags
            provider.refresh()
            if provider.is_enabled("critical_feature"):
                run_critical_operation()
        """
        pass

    def close(self) -> None:
        """
        Clean up resources used by the provider.

        Override this method in subclasses that need cleanup, such as:
            - Closing network connections
            - Stopping background threads
            - Flushing caches to disk
            - Releasing file handles

        This method is called when the application shuts down or
        when switching to a different provider.

        The default implementation does nothing, making it safe
        to call even if no cleanup is needed.

        Example:
            def close(self):
                if self._client:
                    self._client.disconnect()
                    self._client = None
                self._cache.clear()
        """
        pass
