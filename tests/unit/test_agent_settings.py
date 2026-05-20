from src.internhunter.config.settings import load_settings


def test_agent_settings_load_query_limit_policy_from_yaml():
    settings = load_settings()

    assert settings.agent.max_iterations == 5
    assert settings.agent.memory_limit == 10
    assert settings.agent.default_query_limit == 50
    assert settings.agent.max_query_limit == 100
