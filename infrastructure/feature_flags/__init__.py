"""
Feature Flag System for Stock Signal API.

This package provides a unified feature flag interface that automatically
selects the appropriate backend based on the deployment environment:

    - Local Development (APP_ENV=local): Unleash self-hosted server
    - AWS Cloud (APP_ENV=qa/stg/prod): AWS AppConfig

=============================================================================
QUICK START
=============================================================================

Basic Usage:
    from infrastructure.feature_flags import is_feature_enabled, FeatureFlag

    # Check if a feature is enabled
    if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
        run_watchlist_analysis()

    # Check with user targeting (for gradual rollout)
    if is_feature_enabled(FeatureFlag.PREMARKET_ANALYSIS, context={"user_id": "123"}):
        run_premarket_analysis()

Get All Flags:
    from infrastructure.feature_flags import get_all_flags

    flags = get_all_flags()
    # {'single_stock_analysis': True, 'watchlist_analysis': False, ...}

=============================================================================
AVAILABLE FLAGS
=============================================================================

| Flag Name                | Default | Description                          |
|--------------------------|---------|--------------------------------------|
| single_stock_analysis    | True    | Core single stock analysis feature   |
| watchlist_analysis       | False   | Batch analysis of watchlist stocks   |
| premarket_analysis       | False   | Analysis during pre-market hours     |
| aftermarket_analysis     | False   | Analysis during after-market hours   |

=============================================================================
ARCHITECTURE
=============================================================================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                        Application Code                              │
    │                                                                      │
    │  from infrastructure.feature_flags import is_feature_enabled        │
    │  is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS)                 │
    │                                                                      │
    └───────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      FeatureFlagService                              │
    │                    (Auto-selects provider)                           │
    └───────────────────────────────┬─────────────────────────────────────┘
                                    │
                       ┌────────────┴────────────┐
                       │                         │
                       ▼                         ▼
    ┌─────────────────────────────┐ ┌─────────────────────────────┐
    │      UnleashProvider        │ │     AppConfigProvider       │
    │      (APP_ENV=local)        │ │   (APP_ENV=qa/stg/prod)     │
    ├─────────────────────────────┤ ├─────────────────────────────┤
    │  - Docker: localhost:4242   │ │  - Terraform managed        │
    │  - UI for flag management   │ │  - Gradual deployment       │
    │  - 15 second refresh        │ │  - 60 second refresh        │
    └─────────────────────────────┘ └─────────────────────────────┘

=============================================================================
LOCAL DEVELOPMENT SETUP (Unleash)
=============================================================================

1. Start Unleash Server:
    docker compose --profile feature-flags up -d

2. Access Unleash UI:
    http://localhost:4242
    Login: admin / unleash4all

3. Create Feature Flags:
    - Click "New feature flag"
    - Enter flag name (e.g., watchlist_analysis)
    - Toggle enabled state
    - Save

4. Test in Python:
    from infrastructure.feature_flags import get_all_flags
    print(get_all_flags())

=============================================================================
AWS DEPLOYMENT SETUP (AppConfig)
=============================================================================

1. Deploy with Terraform:
    cd terraform/environments/qa
    terraform apply

2. Get AppConfig IDs:
    terraform output appconfig_application_id
    terraform output appconfig_environment_id
    terraform output appconfig_profile_id

3. Configure Environment:
    export APP_ENV=qa
    export APPCONFIG_APPLICATION_ID=<id>
    export APPCONFIG_ENVIRONMENT_ID=<id>
    export APPCONFIG_PROFILE_ID=<id>

4. Enable Flags via Terraform:
    # In terraform.tfvars:
    enable_watchlist_analysis = true

    terraform apply

=============================================================================
MODULE STRUCTURE
=============================================================================

infrastructure/feature_flags/
├── __init__.py              # This file - package exports
├── flags.py                 # FeatureFlag enum and defaults
├── provider.py              # Abstract FeatureFlagProvider interface
├── unleash_provider.py      # Unleash implementation (local)
├── appconfig_provider.py    # AWS AppConfig implementation (cloud)
└── feature_flag_service.py  # Service facade with auto-selection

=============================================================================
API ENDPOINTS
=============================================================================

GET /api/v1/features
    Returns all flag states:
    {
        "flags": {"single_stock_analysis": true, ...},
        "provider": "unleash",
        "environment": "local"
    }

POST /api/v1/features/check
    Check specific flag:
    Request: {"flag_name": "watchlist_analysis", "context": {"user_id": "123"}}
    Response: {"flag_name": "watchlist_analysis", "enabled": false}

=============================================================================
REFERENCES
=============================================================================

- Unleash: https://docs.getunleash.io/
- AWS AppConfig: https://docs.aws.amazon.com/appconfig/
- Feature Flag Best Practices: https://martinfowler.com/articles/feature-toggles.html
"""

# ─────────────────────────────────────────────────────────────────────────────
# Public API Exports
# ─────────────────────────────────────────────────────────────────────────────

# Flag definitions and defaults
from .flags import (
    FeatureFlag,           # Enum of available feature flags
    FEATURE_FLAG_DEFAULTS, # Dict mapping flags to default values
    get_default,           # Function to get default for a flag
)

# Provider interface (for implementing custom providers)
from .provider import FeatureFlagProvider

# Service and convenience functions
from .feature_flag_service import (
    FeatureFlagService,        # Service class (for advanced usage)
    get_feature_flag_service,  # Get singleton service instance
    is_feature_enabled,        # Main function to check flag state
    get_all_flags,             # Get all flags and their states
)

# ─────────────────────────────────────────────────────────────────────────────
# __all__ - Explicit public API
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # ─────────────────────────────────────────────────────────────────────────
    # Enums and Defaults
    # Use these to reference flags and their default values
    # ─────────────────────────────────────────────────────────────────────────
    "FeatureFlag",           # Enum: FeatureFlag.WATCHLIST_ANALYSIS
    "FEATURE_FLAG_DEFAULTS", # Dict: {FeatureFlag.X: True/False}
    "get_default",           # Func: get_default(FeatureFlag.X) -> bool

    # ─────────────────────────────────────────────────────────────────────────
    # Provider Interface
    # Implement this to create custom providers
    # ─────────────────────────────────────────────────────────────────────────
    "FeatureFlagProvider",   # ABC for implementing providers

    # ─────────────────────────────────────────────────────────────────────────
    # Service
    # Use for advanced scenarios or testing
    # ─────────────────────────────────────────────────────────────────────────
    "FeatureFlagService",       # Class: manages provider and checks
    "get_feature_flag_service", # Func: get singleton service instance

    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Functions (Recommended for most use cases)
    # ─────────────────────────────────────────────────────────────────────────
    "is_feature_enabled",    # Func: is_feature_enabled(FeatureFlag.X) -> bool
    "get_all_flags",         # Func: get_all_flags() -> Dict[str, bool]
]
