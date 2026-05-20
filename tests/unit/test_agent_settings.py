from pydantic import SecretStr

from src.internhunter.config.settings import load_settings


def test_agent_settings_load_query_limit_policy_from_yaml():
    """Agent runtime settings should include typed runtime and provider knobs from YAML."""
    settings = load_settings()

    assert settings.app.name == "job-finder"
    assert settings.app.version == "2.0.0"
    assert settings.app.environment == "development"
    assert settings.agent.max_iterations == 5
    assert settings.agent.memory_limit == 10
    assert settings.agent.default_query_limit == 50
    assert settings.agent.max_query_limit == 100
    assert settings.agent.provider.name == "ollama"
    assert settings.agent.provider.model == "qwen3.5:4b"
    assert settings.agent.provider.base_url == "http://127.0.0.1:11434"
    assert settings.agent.provider.temperature == 0.2
    assert settings.llm.primary_provider == "gemini"
    assert settings.llm.fallback_provider == "groq"
    assert settings.llm.validation_model == "gemini-2.5-flash-lite"
    assert settings.llm.rate_limit_rpm == 20
    assert settings.logging.format == "console"
    assert settings.logging.level == "INFO"
    assert settings.mlflow.tracking_uri == "sqlite:///mlflow.db"
    assert settings.mlflow.experiment == "job-finder"


def test_settings_apply_env_overrides_for_deployment_specific_values(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///override.db")
    monkeypatch.setenv("MLFLOW_EXPERIMENT", "override-exp")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-test")

    settings = load_settings()

    assert settings.app.environment == "staging"
    assert settings.ENVIRONMENT == "staging"
    assert settings.mlflow.tracking_uri == "sqlite:///override.db"
    assert settings.mlflow.experiment == "override-exp"
    assert settings.LANGFUSE_HOST == "https://langfuse.example"
    assert isinstance(settings.LANGFUSE_PUBLIC_KEY, SecretStr)
    assert settings.LANGFUSE_PUBLIC_KEY.get_secret_value() == "public-test"
    assert isinstance(settings.LANGFUSE_SECRET_KEY, SecretStr)
    assert settings.LANGFUSE_SECRET_KEY.get_secret_value() == "secret-test"
