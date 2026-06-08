"""
Unleash feature flag provider for local development.

This module implements the FeatureFlagProvider interface using Unleash,
an open-source feature flag management system. It's designed for local
development where a self-hosted Unleash server runs in Docker.

Architecture:
    ┌─────────────────┐      ┌─────────────────┐
    │ UnleashProvider │ ---> │  Unleash Server │
    │   (Python SDK)  │      │  (Docker:4242)  │
    └─────────────────┘      └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │   PostgreSQL    │
                             │   (unleash db)  │
                             └─────────────────┘

Setup:
    1. Start Unleash: docker compose --profile feature-flags up -d
    2. Access UI: http://localhost:4242 (admin / unleash4all)
    3. Create feature flags in the UI
    4. Use this provider to check flag states

Configuration:
    Environment Variables:
        UNLEASH_URL: Unleash server API URL (default: http://localhost:4242/api)
        UNLEASH_APP_NAME: Application name for Unleash (default: stock-signal-api)
        UNLEASH_API_TOKEN: Client API token (default: insecure dev token)
        UNLEASH_CACHE_DIRECTORY: Local SDK cache directory
                                 (default: ~/Caches/stock-signal-api)

    application.yml:
        feature_flags:
          unleash:
            url: "http://localhost:4242/api"
            app_name: "stock-signal-api"
            refresh_interval_seconds: 15

Dependencies:
    pip install UnleashClient>=5.11.0

References:
    - Unleash Python SDK: https://github.com/Unleash/unleash-client-python
    - Unleash Docs: https://docs.getunleash.io/
    - Unleash Docker: https://hub.docker.com/r/unleashorg/unleash-server
"""

import os
from typing import Dict, Optional

from .provider import FeatureFlagProvider
from .flags import FeatureFlag, FEATURE_FLAG_DEFAULTS


class UnleashProvider(FeatureFlagProvider):
    """
    Unleash feature flag provider for local development.

    This provider connects to a self-hosted Unleash server using the
    official Python SDK. It supports:
        - Automatic background refresh of flag states
        - User/session targeting for gradual rollouts
        - Graceful fallback to defaults when Unleash is unavailable

    Thread Safety:
        The Unleash SDK handles thread safety internally. Multiple threads
        can safely call is_enabled() concurrently.

    Caching:
        The SDK caches flag states locally and refreshes them in the
        background every `refresh_interval` seconds.

    Attributes:
        url: Unleash server API URL
        app_name: Application identifier in Unleash
        api_token: Authentication token for the Unleash API
        refresh_interval: How often to refresh flags (seconds)

    Example:
        # Create provider with custom settings
        provider = UnleashProvider(
            url="http://localhost:4242/api",
            app_name="my-app",
            refresh_interval=30
        )

        # Check if a flag is enabled
        if provider.is_enabled("new_feature"):
            use_new_feature()

        # Clean up when done
        provider.close()
    """

    def __init__(
        self,
        url: str = None,
        app_name: str = None,
        api_token: str = None,
        refresh_interval: int = 15,
    ):
        """
        Initialize the Unleash provider.

        The provider will attempt to connect to the Unleash server
        immediately. If the connection fails or the SDK is not installed,
        it will fall back to using default flag values.

        Args:
            url: Unleash server API URL.
                 Default: UNLEASH_URL env var or http://localhost:4242/api

            app_name: Application name registered in Unleash.
                      This appears in the Unleash UI under "Applications".
                      Default: UNLEASH_APP_NAME env var or stock-signal-api

            api_token: Client API token for authentication.
                       Create tokens in Unleash UI: Admin > API Access
                       Default: UNLEASH_API_TOKEN env var or dev token

            refresh_interval: How often to poll for flag updates (seconds).
                             Lower values = more API calls but fresher data.
                             Default: 15 seconds

        Raises:
            No exceptions are raised. Failures are logged and the provider
            falls back to default values.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Instance State
        # ─────────────────────────────────────────────────────────────────────

        # Unleash SDK client instance (lazy-loaded)
        self._client = None

        # Whether the client was successfully initialized
        self._initialized = False

        # Local cache for flag values (used as fallback)
        self._cache: Dict[str, bool] = {}

        # ─────────────────────────────────────────────────────────────────────
        # Configuration
        # Priority: Constructor args > Environment variables > Defaults
        # ─────────────────────────────────────────────────────────────────────

        # Unleash server URL - must include /api suffix
        self.url = url or os.getenv("UNLEASH_URL", "http://localhost:4242/api")

        # Application name - identifies this app in Unleash UI
        self.app_name = app_name or os.getenv("UNLEASH_APP_NAME", "stock-signal-api")

        # API token - use client token, not admin token
        # Format: [project]:[environment].[token]
        # The default is the insecure development token from docker-compose.yml
        self.api_token = api_token or os.getenv(
            "UNLEASH_API_TOKEN",
            "default:development.unleash-insecure-api-token",
        )

        # Refresh interval in seconds (how often SDK polls for updates)
        self.refresh_interval = refresh_interval

        # Local cache directory for Unleash SDK bootstrap/toggle cache
        self.cache_directory = os.getenv(
            "UNLEASH_CACHE_DIRECTORY",
            os.path.expanduser("~/Caches/stock-signal-api"),
        )

        # ─────────────────────────────────────────────────────────────────────
        # Initialize Connection
        # ─────────────────────────────────────────────────────────────────────

        self._initialize_client()

    def _initialize_client(self) -> None:
        """
        Initialize the Unleash SDK client.

        This method:
            1. Imports the UnleashClient (may fail if not installed)
            2. Creates a client instance with our configuration
            3. Calls initialize_client() to fetch initial flag states
            4. Sets _initialized = True on success

        Error Handling:
            - ImportError: UnleashClient package not installed
            - ConnectionError: Cannot reach Unleash server
            - Other exceptions: Logged and treated as initialization failure

        On failure, _initialized remains False and all flag checks
        will return default values.
        """
        try:
            # Import the Unleash SDK
            # This will raise ImportError if UnleashClient is not installed
            from UnleashClient import UnleashClient

            # Create the cache directory. If the configured location is not
            # writable, fall back to a temporary directory.
            try:
                os.makedirs(self.cache_directory, exist_ok=True)
            except OSError:
                fallback_cache_dir = "/tmp/stock-signal-api"
                os.makedirs(fallback_cache_dir, exist_ok=True)
                self.cache_directory = fallback_cache_dir

            # Create the client instance
            # The client doesn't connect until initialize_client() is called
            self._client = UnleashClient(
                url=self.url,
                app_name=self.app_name,
                # Authentication via custom header (Unleash expects this format)
                custom_headers={"Authorization": self.api_token},
                # Background refresh interval
                refresh_interval=self.refresh_interval,
                # Persist SDK cache in user home so local runs can bootstrap quickly
                cache_directory=self.cache_directory,
            )

            # Initialize the client - this fetches flags from the server
            # and starts the background refresh thread
            self._client.initialize_client()

            # Mark as successfully initialized
            self._initialized = True

        except ImportError:
            # UnleashClient package not installed
            # This is expected in production where we use AppConfig instead
            print("[FeatureFlags] UnleashClient not installed, using defaults")
            self._initialized = False

        except Exception as e:
            # Connection error, auth error, or other issue
            # Log the error and continue with defaults
            print(f"[FeatureFlags] Failed to initialize Unleash client: {e}")
            self._initialized = False

    def is_enabled(
        self,
        flag_name: str,
        default: bool = False,
        context: Optional[Dict] = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        This method queries the Unleash SDK for the flag's state.
        If Unleash is unavailable, it returns the default value.

        Args:
            flag_name: Name of the feature flag to check.
                      Can be a string or FeatureFlag enum.

            default: Value to return if flag is not found or on error.
                    If not provided, uses FEATURE_FLAG_DEFAULTS.

            context: Optional targeting context for gradual rollouts.
                    Supported keys:
                    - user_id: Maps to Unleash userId
                    - session_id: Maps to Unleash sessionId
                    - Other keys: Added to Unleash properties

        Returns:
            bool: True if the flag is enabled, False otherwise.

        Example:
            # Simple check
            if provider.is_enabled("new_feature"):
                use_new_feature()

            # With user targeting (for percentage rollout)
            if provider.is_enabled("beta", context={"user_id": "user123"}):
                show_beta_ui()
        """
        # ─────────────────────────────────────────────────────────────────────
        # Normalize Input
        # ─────────────────────────────────────────────────────────────────────

        # Convert FeatureFlag enum to string if needed
        # This allows callers to use either string or enum
        if isinstance(flag_name, FeatureFlag):
            flag_name = flag_name.value

        # ─────────────────────────────────────────────────────────────────────
        # Determine Default Value
        # ─────────────────────────────────────────────────────────────────────

        # Look up the default from FEATURE_FLAG_DEFAULTS if the flag is known
        # This ensures consistent defaults across the application
        try:
            flag_enum = FeatureFlag(flag_name)
            default = FEATURE_FLAG_DEFAULTS.get(flag_enum, default)
        except ValueError:
            # Unknown flag - use the provided default
            pass

        # ─────────────────────────────────────────────────────────────────────
        # Check Initialization
        # ─────────────────────────────────────────────────────────────────────

        # If Unleash isn't available, return the default
        if not self._initialized or self._client is None:
            return default

        # ─────────────────────────────────────────────────────────────────────
        # Query Unleash
        # ─────────────────────────────────────────────────────────────────────

        try:
            # Build Unleash context from our context dict
            # Unleash uses specific field names (userId, sessionId)
            unleash_context = {}

            if context:
                # Map our context keys to Unleash's expected format
                if "user_id" in context:
                    # userId is used for user-based targeting/rollouts
                    unleash_context["userId"] = str(context["user_id"])

                if "session_id" in context:
                    # sessionId is used for session-based experiments
                    unleash_context["sessionId"] = str(context["session_id"])

                # Any other context keys go into properties
                # These can be used in custom strategies
                unleash_context["properties"] = {
                    k: str(v) for k, v in context.items()
                    if k not in ("user_id", "session_id")
                }

            # Call the Unleash SDK to check the flag
            # The fallback_function is called if the flag doesn't exist
            return self._client.is_enabled(
                flag_name,
                context=unleash_context if unleash_context else None,
                # Fallback function - called when flag not found
                fallback_function=lambda *args, **kwargs: default,
            )

        except Exception as e:
            # Log any errors and return the default
            print(f"[FeatureFlags] Error checking flag {flag_name}: {e}")
            return default

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.

        Returns:
            Dict[str, bool]: Dictionary mapping flag names to their states.

        Example:
            >>> provider.get_all_flags()
            {
                'single_stock_analysis': True,
                'watchlist_analysis': False,
                'premarket_analysis': False,
                'aftermarket_analysis': False
            }
        """
        # Iterate through all known flags and check each one
        flags = {}
        for flag in FeatureFlag:
            flags[flag.value] = self.is_enabled(flag)
        return flags

    def refresh(self) -> None:
        """
        Refresh the feature flag cache from Unleash.

        The Unleash SDK automatically refreshes in the background,
        but this method allows forcing an immediate refresh.

        Use cases:
            - After deploying new flag configurations
            - Before critical operations that depend on flags
            - For testing/debugging
        """
        if self._initialized and self._client is not None:
            try:
                # Force the SDK to fetch latest flags from the server
                # This is synchronous and blocks until complete
                self._client.fetch_and_load_toggle_features()
            except Exception as e:
                print(f"[FeatureFlags] Error refreshing flags: {e}")

    def close(self) -> None:
        """
        Clean up the Unleash client.

        This method:
            1. Stops the background refresh thread
            2. Closes network connections
            3. Clears the client reference

        Call this when shutting down the application or
        switching to a different provider.
        """
        if self._client is not None:
            try:
                # destroy() stops background threads and cleans up resources
                self._client.destroy()
            except Exception:
                # Ignore errors during cleanup
                pass

            # Clear references
            self._client = None
            self._initialized = False
