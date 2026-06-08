"""
AWS AppConfig feature flag provider for cloud environments.

This module implements the FeatureFlagProvider interface using AWS AppConfig,
Amazon's managed feature flag and configuration service. It's designed for
QA, Staging, and Production environments running on AWS.

Architecture:
    ┌───────────────────┐      ┌─────────────────────┐
    │ AppConfigProvider │ ---> │    AWS AppConfig    │
    │   (boto3 SDK)     │      │  (Managed Service)  │
    └───────────────────┘      └──────────┬──────────┘
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         │                                │                                │
         ▼                                ▼                                ▼
    ┌──────────┐                   ┌──────────────┐                ┌────────────┐
    │Application│                   │ Environment  │                │   Config   │
    │stock-signal│                  │  qa/stg/prod │                │  Profile   │
    └──────────┘                   └──────────────┘                └────────────┘

AWS AppConfig Concepts:
    - Application: Logical grouping (e.g., "stock-signal-qa")
    - Environment: Deployment target (e.g., "qa", "stg", "prod")
    - Configuration Profile: The actual flags configuration
    - Deployment: Process of rolling out a new configuration

Setup:
    1. Deploy with Terraform: cd terraform/environments/qa && terraform apply
    2. Get IDs from output: terraform output appconfig_*
    3. Set environment variables or pass to constructor

Configuration:
    Environment Variables:
        APP_ENV: Environment name (qa, stg, prod) - triggers AWS mode
        APPCONFIG_APPLICATION_ID: AppConfig application ID
        APPCONFIG_ENVIRONMENT_ID: AppConfig environment ID
        APPCONFIG_PROFILE_ID: AppConfig configuration profile ID
        AWS_REGION: AWS region (default: us-east-1)

IAM Permissions Required:
    - appconfig:StartConfigurationSession
    - appconfig:GetLatestConfiguration

Dependencies:
    pip install boto3>=1.34.0

References:
    - AWS AppConfig: https://docs.aws.amazon.com/appconfig/
    - AppConfig Feature Flags: https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile-feature-flags.html
    - boto3 AppConfigData: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/appconfigdata.html
"""

import json
import os
import time
from typing import Dict, Optional

from .provider import FeatureFlagProvider
from .flags import FeatureFlag, FEATURE_FLAG_DEFAULTS


class AppConfigProvider(FeatureFlagProvider):
    """
    AWS AppConfig feature flag provider for QA/STG/PROD environments.

    This provider uses AWS AppConfig's GetLatestConfiguration API to fetch
    feature flag states. It implements:
        - Session-based polling (required by AppConfig)
        - Local caching to minimize API calls
        - Automatic refresh based on poll interval
        - Graceful fallback to defaults when unavailable

    Session Management:
        AppConfig uses a session-based model where:
        1. You start a session and get an initial token
        2. Each GetLatestConfiguration call returns a new token
        3. The token must be used for the next call

    Caching:
        Flag values are cached locally and only refreshed when:
        - The poll interval has elapsed
        - refresh() is called manually
        - AppConfig returns new configuration

    Cost Optimization:
        AppConfig charges per configuration request. The poll_interval_seconds
        setting controls how often we fetch new configurations.
        Default: 60 seconds (1 call per minute = ~43,200 calls/month)

    Attributes:
        application_id: AppConfig application identifier
        environment_id: AppConfig environment identifier
        profile_id: AppConfig configuration profile identifier
        poll_interval_seconds: How often to poll for updates
        region: AWS region where AppConfig is deployed

    Example:
        # Create provider with explicit IDs
        provider = AppConfigProvider(
            application_id="abc123",
            environment_id="def456",
            profile_id="ghi789",
            poll_interval_seconds=60
        )

        # Or use environment variables
        # export APPCONFIG_APPLICATION_ID=abc123
        # export APPCONFIG_ENVIRONMENT_ID=def456
        # export APPCONFIG_PROFILE_ID=ghi789
        provider = AppConfigProvider()

        # Check flags
        if provider.is_enabled("new_feature"):
            use_new_feature()
    """

    def __init__(
        self,
        application_id: str = None,
        environment_id: str = None,
        profile_id: str = None,
        poll_interval_seconds: int = 60,
        region: str = None,
    ):
        """
        Initialize the AppConfig provider.

        The provider will attempt to start a configuration session with
        AppConfig immediately. If the connection fails, it will fall back
        to using default flag values.

        Args:
            application_id: AppConfig application ID.
                           Get from Terraform output or AWS Console.
                           Default: APPCONFIG_APPLICATION_ID env var

            environment_id: AppConfig environment ID.
                           Get from Terraform output or AWS Console.
                           Default: APPCONFIG_ENVIRONMENT_ID env var

            profile_id: AppConfig configuration profile ID.
                       Get from Terraform output or AWS Console.
                       Default: APPCONFIG_PROFILE_ID env var

            poll_interval_seconds: How often to poll for config updates.
                                  AppConfig enforces a minimum of 15 seconds.
                                  Default: 60 seconds

            region: AWS region where AppConfig is deployed.
                   Default: AWS_REGION env var or us-east-1

        Raises:
            No exceptions are raised. Failures are logged and the provider
            falls back to default values.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Instance State
        # ─────────────────────────────────────────────────────────────────────

        # boto3 AppConfigData client (lazy-loaded)
        self._client = None

        # Whether the client was successfully initialized
        self._initialized = False

        # Local cache for flag values
        # Key: flag name, Value: enabled state
        self._cache: Dict[str, bool] = {}

        # Timestamp of last poll (for rate limiting)
        self._last_poll_time: float = 0

        # Configuration token for session continuity
        # AppConfig requires this token for each GetLatestConfiguration call
        self._configuration_token: Optional[str] = None

        # ─────────────────────────────────────────────────────────────────────
        # Configuration
        # Priority: Constructor args > Environment variables > Defaults
        # ─────────────────────────────────────────────────────────────────────

        # AppConfig identifiers - all three are required
        self.application_id = application_id or os.getenv("APPCONFIG_APPLICATION_ID", "")
        self.environment_id = environment_id or os.getenv("APPCONFIG_ENVIRONMENT_ID", "")
        self.profile_id = profile_id or os.getenv("APPCONFIG_PROFILE_ID", "")

        # Poll interval - how often to check for updates
        # AppConfig enforces a minimum of 15 seconds
        self.poll_interval_seconds = poll_interval_seconds

        # AWS region
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        # ─────────────────────────────────────────────────────────────────────
        # Initialize Connection
        # ─────────────────────────────────────────────────────────────────────

        self._initialize_client()

    def _initialize_client(self) -> None:
        """
        Initialize the AWS AppConfig Data client.

        This method:
            1. Validates that all required IDs are configured
            2. Creates a boto3 appconfigdata client
            3. Starts a configuration session
            4. Fetches the initial configuration

        Error Handling:
            - Missing IDs: Logs warning and uses defaults
            - ImportError: boto3 not installed
            - AWS errors: Connection issues, permission denied, etc.

        On failure, _initialized remains False and all flag checks
        will return default values.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Validate Configuration
        # ─────────────────────────────────────────────────────────────────────

        # All three IDs are required to connect to AppConfig
        if not all([self.application_id, self.environment_id, self.profile_id]):
            print("[FeatureFlags] AppConfig IDs not configured, using defaults")
            return

        # ─────────────────────────────────────────────────────────────────────
        # Create Client and Start Session
        # ─────────────────────────────────────────────────────────────────────

        try:
            # Import boto3 (may fail if not installed)
            import boto3

            # Create the AppConfigData client
            # Note: We use 'appconfigdata' service, not 'appconfig'
            # The appconfigdata service is optimized for runtime flag checks
            self._client = boto3.client(
                "appconfigdata",
                region_name=self.region,
            )

            # Start a configuration session
            # This returns a token that must be used for subsequent requests
            # The session automatically handles:
            #   - Configuration caching on AWS side
            #   - Change detection (only returns data if changed)
            response = self._client.start_configuration_session(
                ApplicationIdentifier=self.application_id,
                EnvironmentIdentifier=self.environment_id,
                ConfigurationProfileIdentifier=self.profile_id,
                # Minimum poll interval - AppConfig enforces this
                RequiredMinimumPollIntervalInSeconds=self.poll_interval_seconds,
            )

            # Store the initial token for the first GetLatestConfiguration call
            self._configuration_token = response["InitialConfigurationToken"]

            # Mark as initialized
            self._initialized = True

            # Fetch the initial configuration
            self._fetch_configuration()

        except ImportError:
            # boto3 not installed - expected in local development
            print("[FeatureFlags] boto3 not installed, using defaults")

        except Exception as e:
            # AWS error - permission denied, network issue, etc.
            print(f"[FeatureFlags] Failed to initialize AppConfig client: {e}")

    def _fetch_configuration(self) -> None:
        """
        Fetch the latest configuration from AppConfig.

        This method:
            1. Calls GetLatestConfiguration with the current token
            2. Updates the token for the next request
            3. Parses the configuration if new data is returned
            4. Updates the local cache

        AppConfig Behavior:
            - If configuration hasn't changed, response.Configuration is empty
            - If configuration changed, response.Configuration contains the new data
            - Each response includes NextPollConfigurationToken for the next call

        Error Handling:
            Errors are logged but don't raise exceptions. The cache
            retains its previous values on error.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Validate State
        # ─────────────────────────────────────────────────────────────────────

        # Can't fetch without initialization
        if not self._initialized or self._client is None or not self._configuration_token:
            return

        # ─────────────────────────────────────────────────────────────────────
        # Fetch Configuration
        # ─────────────────────────────────────────────────────────────────────

        try:
            # Call GetLatestConfiguration
            # This is the main API for retrieving flag values
            response = self._client.get_latest_configuration(
                ConfigurationToken=self._configuration_token,
            )

            # Always update the token for the next request
            # Using an old token will cause an error
            self._configuration_token = response["NextPollConfigurationToken"]

            # Check if there's new configuration data
            # If the configuration hasn't changed, this will be empty
            content = response["Configuration"].read()

            if content:
                # New configuration available - parse it
                config = json.loads(content.decode("utf-8"))
                self._parse_feature_flags(config)

            # Update the poll timestamp
            self._last_poll_time = time.time()

        except Exception as e:
            # Log the error but don't crash
            # The cache retains previous values
            print(f"[FeatureFlags] Error fetching AppConfig configuration: {e}")

    def _parse_feature_flags(self, config: dict) -> None:
        """
        Parse feature flags from AppConfig configuration.

        This method handles the AWS AppConfig Feature Flags format,
        which has a specific structure for defining flags and their values.

        AWS AppConfig Feature Flags Format:
            {
                "version": "1",
                "flags": {
                    "flag_name": {
                        "name": "Human Readable Name",
                        "description": "What this flag does"
                    }
                },
                "values": {
                    "flag_name": {
                        "enabled": true
                    }
                }
            }

        The "flags" section defines flag metadata.
        The "values" section contains the actual enabled/disabled state.

        Args:
            config: Parsed JSON configuration from AppConfig
        """
        # ─────────────────────────────────────────────────────────────────────
        # Parse AWS Feature Flags Format
        # ─────────────────────────────────────────────────────────────────────

        # Get the flags definition (metadata about each flag)
        flags = config.get("flags", {})

        # Get the flag values (actual enabled/disabled states)
        values = config.get("values", {})

        # Process each defined flag
        for flag_name, flag_def in flags.items():
            # Check if there's a value for this flag
            if flag_name in values:
                # Use the value from the values section
                # This is the runtime state of the flag
                self._cache[flag_name] = values[flag_name].get("enabled", False)
            else:
                # No value defined - use the default from flag definition
                self._cache[flag_name] = flag_def.get("default", False)

    def _should_poll(self) -> bool:
        """
        Check if it's time to poll for updates.

        AppConfig enforces a minimum poll interval to prevent excessive
        API calls. This method ensures we respect that interval.

        Returns:
            bool: True if enough time has passed since the last poll,
                  False otherwise.
        """
        return time.time() - self._last_poll_time >= self.poll_interval_seconds

    def is_enabled(
        self,
        flag_name: str,
        default: bool = False,
        context: Optional[Dict] = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        This method checks the local cache for the flag's state.
        If the poll interval has elapsed, it first fetches new
        configuration from AppConfig.

        Args:
            flag_name: Name of the feature flag to check.
                      Can be a string or FeatureFlag enum.

            default: Value to return if flag is not found or on error.
                    If not provided, uses FEATURE_FLAG_DEFAULTS.

            context: Optional targeting context.
                    Note: AppConfig Feature Flags don't support targeting
                    in the same way Unleash does. This parameter is
                    accepted for interface compatibility but not used.

        Returns:
            bool: True if the flag is enabled, False otherwise.

        Example:
            if provider.is_enabled("watchlist_analysis"):
                run_watchlist_analysis()
        """
        # ─────────────────────────────────────────────────────────────────────
        # Normalize Input
        # ─────────────────────────────────────────────────────────────────────

        # Convert FeatureFlag enum to string if needed
        if isinstance(flag_name, FeatureFlag):
            flag_name = flag_name.value

        # ─────────────────────────────────────────────────────────────────────
        # Determine Default Value
        # ─────────────────────────────────────────────────────────────────────

        # Look up the default from FEATURE_FLAG_DEFAULTS if the flag is known
        try:
            flag_enum = FeatureFlag(flag_name)
            default = FEATURE_FLAG_DEFAULTS.get(flag_enum, default)
        except ValueError:
            # Unknown flag - use the provided default
            pass

        # ─────────────────────────────────────────────────────────────────────
        # Poll for Updates if Needed
        # ─────────────────────────────────────────────────────────────────────

        # Check if it's time to refresh the configuration
        if self._should_poll():
            self._fetch_configuration()

        # ─────────────────────────────────────────────────────────────────────
        # Return Cached Value or Default
        # ─────────────────────────────────────────────────────────────────────

        # Check the cache first
        if flag_name in self._cache:
            return self._cache[flag_name]

        # Flag not in cache - return default
        return default

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.

        This method ensures the cache is fresh before returning values.

        Returns:
            Dict[str, bool]: Dictionary mapping flag names to their states.

        Example:
            >>> provider.get_all_flags()
            {
                'single_stock_analysis': True,
                'watchlist_analysis': True,
                'premarket_analysis': False,
                'aftermarket_analysis': False
            }
        """
        # Ensure we have the latest configuration
        if self._should_poll():
            self._fetch_configuration()

        # Build the response from all known flags
        flags = {}
        for flag in FeatureFlag:
            flags[flag.value] = self.is_enabled(flag)
        return flags

    def refresh(self) -> None:
        """
        Refresh the feature flag cache from AppConfig.

        Forces an immediate fetch of the configuration, regardless
        of the poll interval. Useful for:
            - Testing configuration changes
            - Ensuring fresh data before critical operations
        """
        self._fetch_configuration()

    def close(self) -> None:
        """
        Clean up the AppConfig client.

        This method releases resources and clears the cache.
        Call this when shutting down or switching providers.
        """
        # Clear the client reference
        self._client = None

        # Reset state
        self._initialized = False

        # Clear the cache
        self._cache.clear()
