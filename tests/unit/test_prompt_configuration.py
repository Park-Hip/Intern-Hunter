from src.internhunter.config.settings import settings


def test_render_prompt_renders_translate_template():
    rendered = settings.render_prompt("translate_to_english", text="Mo ta cong viec")

    assert "Mo ta cong viec" in rendered
    assert "{{ text }}" not in rendered


def test_render_prompt_renders_job_validation_snippet():
    rendered = settings.render_prompt("job_validation", text_snippet="Verify you are human")

    assert "Verify you are human" in rendered
    assert '"is_job": boolean' in rendered
