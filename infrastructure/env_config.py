"""Environment-based configuration for Local (minikube) vs AWS (EKS) deployments."""

import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Environment(Enum):
    """Supported deployment environments."""
    LOCAL = "local"
    QA = "qa"
    STG = "stg"
    PROD = "prod"


@dataclass
class EnvironmentConfig:
    """Configuration for the current environment."""
    env: Environment
    is_aws: bool
    aws_region: str

    # LLM Configuration
    llm_provider: str  # "ollama", "openai", or "bedrock"
    llm_model: str

    # Kafka Configuration
    kafka_bootstrap_servers: str
    kafka_use_msk: bool

    # Vector DB Configuration
    vector_db_type: str  # "qdrant" or "opensearch"
    vector_db_endpoint: str

    # EKS/Kubernetes
    eks_cluster_name: Optional[str] = None

    # Feature flags
    use_secrets_manager: bool = False


def get_environment() -> Environment:
    """Get the current environment from APP_ENV variable."""
    app_env = os.getenv("APP_ENV", "local").lower()

    env_map = {
        "local": Environment.LOCAL,
        "qa": Environment.QA,
        "stg": Environment.STG,
        "staging": Environment.STG,
        "prod": Environment.PROD,
        "production": Environment.PROD,
    }

    return env_map.get(app_env, Environment.LOCAL)


def is_aws_environment() -> bool:
    """Check if running in an AWS environment (QA, STG, or PROD)."""
    return get_environment() != Environment.LOCAL


def get_aws_region() -> str:
    """Get the AWS region for the current environment."""
    return os.getenv("AWS_REGION", "us-east-1")


def get_environment_config() -> EnvironmentConfig:
    """Get the full configuration for the current environment."""
    env = get_environment()
    is_aws = env != Environment.LOCAL
    aws_region = get_aws_region()

    if is_aws:
        # AWS Configuration (QA, STG, PROD)
        env_prefix = env.value.upper()

        return EnvironmentConfig(
            env=env,
            is_aws=True,
            aws_region=aws_region,

            # Use AWS Bedrock for LLM
            llm_provider="bedrock",
            llm_model=os.getenv("BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0"),

            # Use Amazon MSK for Kafka
            kafka_bootstrap_servers=os.getenv(
                "MSK_BOOTSTRAP_SERVERS",
                f"msk.stock-signal-{env.value}.{aws_region}.amazonaws.com:9092"
            ),
            kafka_use_msk=True,

            # Use Amazon OpenSearch for vector DB
            vector_db_type="opensearch",
            vector_db_endpoint=os.getenv(
                "OPENSEARCH_ENDPOINT",
                f"https://opensearch.stock-signal-{env.value}.{aws_region}.es.amazonaws.com"
            ),

            # EKS cluster
            eks_cluster_name=os.getenv("EKS_CLUSTER_NAME", f"stock-signal-{env.value}"),

            # Use AWS Secrets Manager
            use_secrets_manager=True,
        )
    else:
        # Local Configuration (minikube)
        return EnvironmentConfig(
            env=env,
            is_aws=False,
            aws_region=aws_region,

            # Use Ollama or OpenAI for LLM
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            llm_model=os.getenv("LLM_MODEL", "ollama/llama3.1"),

            # Use self-hosted Kafka
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            kafka_use_msk=False,

            # Use Qdrant for vector DB
            vector_db_type="qdrant",
            vector_db_endpoint=os.getenv("QDRANT_URL", "http://localhost:6333"),

            # No EKS
            eks_cluster_name=None,

            # No Secrets Manager
            use_secrets_manager=False,
        )


def get_llm_model_id() -> str:
    """Get the LLM model ID for LiteLLM based on environment."""
    config = get_environment_config()

    if config.llm_provider == "bedrock":
        # LiteLLM uses bedrock/ prefix for AWS Bedrock models
        return f"bedrock/{config.llm_model}"
    elif config.llm_provider == "ollama":
        # LiteLLM uses ollama/ prefix for Ollama models
        if not config.llm_model.startswith("ollama/"):
            return f"ollama/{config.llm_model}"
        return config.llm_model
    else:
        # OpenAI or other providers
        return config.llm_model


def print_environment_info():
    """Print current environment configuration for debugging."""
    config = get_environment_config()
    print(f"  [EnvConfig] Environment: {config.env.value.upper()}")
    print(f"  [EnvConfig] AWS Mode: {config.is_aws}")
    if config.is_aws:
        print(f"  [EnvConfig] AWS Region: {config.aws_region}")
        print(f"  [EnvConfig] EKS Cluster: {config.eks_cluster_name}")
    print(f"  [EnvConfig] LLM Provider: {config.llm_provider} ({config.llm_model})")
    print(f"  [EnvConfig] Vector DB: {config.vector_db_type}")
    print(f"  [EnvConfig] Kafka: {'MSK' if config.kafka_use_msk else 'Self-hosted'}")
