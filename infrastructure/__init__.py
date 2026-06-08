"""Infrastructure utilities for Stock Signal Generator."""

from infrastructure.config import Config, APP_ENV, IS_AWS, AWS_REGION
from infrastructure.env_config import (
    Environment,
    EnvironmentConfig,
    get_environment,
    get_environment_config,
    is_aws_environment,
    get_aws_region,
    get_llm_model_id,
)

# Report utils are imported lazily to avoid conflicts with other libraries
# Use: from infrastructure.report_utils import generate_pdf_report

# AWS services are imported lazily to avoid boto3 dependency in local environments
# Use: from infrastructure.aws_services import BedrockClient, MSKClient
# Use: from infrastructure.opensearch_store import OpenSearchStore, get_vector_store
# Use: from infrastructure.secrets_manager import get_secret, get_secrets_manager

__all__ = [
    # Config
    "Config",
    "APP_ENV",
    "IS_AWS",
    "AWS_REGION",
    # Environment
    "Environment",
    "EnvironmentConfig",
    "get_environment",
    "get_environment_config",
    "is_aws_environment",
    "get_aws_region",
    "get_llm_model_id",
]
