import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.internhunter.extraction.job_processor import (
    JobProcessor,
    build_deterministic_processed_job,
    build_llm_job_context,
    build_topcv_parser_hints,
    build_validation_text,
    extract_direct_topcv_sections,
)
from src.internhunter.storage.repositories.etl import ETLRepository
from src.internhunter.storage.models import RawJobDB, AuditJobDB
from src.core.models import ProcessedJob
from src.internhunter.llm.base import LLMProvider
from src.internhunter.llm.providers import _build_prompt
from src.internhunter.extraction.validator import JobValidator


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "topcv"

@pytest.fixture
def repo(test_db_session):
    return ETLRepository()

@pytest.fixture
def processor(mock_gemini_client):
    # The processor uses the mocked Gemini client automatically 
    # thanks to the monkeypatching in the fixture.
    return JobProcessor()


def load_processed_job_fixture(name: str) -> ProcessedJob:
    payload = json.loads((FIXTURE_DIR / f"{name}.extracted.json").read_text(encoding="utf-8"))
    return ProcessedJob(**payload)


def get_latest_audit_row(test_db_session):
    return test_db_session.query(AuditJobDB).order_by(AuditJobDB.id.desc()).first()


class DummyProvider(LLMProvider):
    def process_raw_job(self, job_data):  # pragma: no cover - not used directly in tests
        raise NotImplementedError

    def translate(self, text: str):  # pragma: no cover - not used directly in tests
        raise NotImplementedError


def test_llm_provider_prefers_structured_topcv_context_over_conflicting_info():
    job = SimpleNamespace(
        title="Raw Title",
        location="Unknown",
        raw_markdown="Fallback markdown that should only be used when structured fields are absent.",
        full_json_dump=json.dumps(
            {
                "title": "Raw Title",
                "company": "TopCV",
                "location": "Hanoi",
                "info": "Legacy conflicting blob that should not win.",
                "description": "Structured description from raw JSON.",
                "requirements": "Structured requirements from raw JSON.",
                "benefits": "Structured benefits from raw JSON.",
                "work_location": "HÃ  Ná»™i",
                "working_time": "Mon-Fri",
                "application_method": "Apply online",
            },
            ensure_ascii=False,
        ),
    )

    provider = DummyProvider()
    raw_context, description, requirement, benefit, work_location, working_time, application_method = provider._prepare_job_context(job)

    assert description == "Structured description from raw JSON."
    assert requirement == "Structured requirements from raw JSON."
    assert benefit == "Structured benefits from raw JSON."
    assert work_location == "HÃ  Ná»™i"
    assert working_time == "Mon-Fri"
    assert application_method == "Apply online"
    assert raw_context["description"] == "Structured description from raw JSON."
    assert raw_context["requirements"] == "Structured requirements from raw JSON."
    assert raw_context["benefits"] == "Structured benefits from raw JSON."


def test_processor_contract_helpers_keep_direct_facts_and_parser_hints_separate():
    job = SimpleNamespace(
        title="Raw Title",
        location="Unknown",
        raw_markdown="Fallback markdown with enough detail to infer the legacy description.",
        full_json_dump=json.dumps(
            {
                "title": "Raw Title",
                "company": "TopCV",
                "location": "Hanoi",
                "info": "Legacy info that should stay as fallback.",
                "description": "Structured description from raw JSON.",
                "requirements": "Structured requirements from raw JSON.",
                "benefits": "Structured benefits from raw JSON.",
                "work_location": "HÃ  Ná»™i",
                "working_time": "Mon-Fri",
                "application_method": "Apply online",
            },
            ensure_ascii=False,
        ),
    )
    job.model_copy = lambda update=None: SimpleNamespace(**{**job.__dict__, **(update or {})})

    raw_context = json.loads(job.full_json_dump)
    direct_sections = extract_direct_topcv_sections(job, raw_context)
    parser_hints = build_topcv_parser_hints(job, raw_context)
    llm_job = build_llm_job_context(job)
    deterministic_job = build_deterministic_processed_job(job)

    assert direct_sections == {
        "description": "Structured description from raw JSON.",
        "requirement": "Structured requirements from raw JSON.",
        "benefit": "Structured benefits from raw JSON.",
    }
    assert parser_hints["location_hint"] == "HÃ  Ná»™i"
    assert parser_hints["cities"] == ["HÃ  Ná»™i"]
    assert parser_hints["is_internship"] is False
    assert "Structured description from raw JSON." in llm_job.full_json_dump
    assert "HÃ  Ná»™i" == llm_job.location
    assert deterministic_job.description == "Structured description from raw JSON."
    assert deterministic_job.requirement == "Structured requirements from raw JSON."
    assert deterministic_job.benefit == "Structured benefits from raw JSON."
    assert deterministic_job.cities == ["HÃ  Ná»™i"]
    assert deterministic_job.company == "TopCV"


def test_llm_provider_uses_legacy_info_and_raw_markdown_when_structured_fields_are_missing():
    job = SimpleNamespace(
        title="Legacy Title",
        location="Hanoi",
        raw_markdown=None,
        full_json_dump=json.dumps(
            {
                "title": "Legacy Title",
                "company": "TopCV",
                "location": "Hanoi",
                "info": (
                    "Mô tả công việc\n"
                    "Legacy info description.\n\n"
                    "Yêu cầu ứng viên\n"
                    "Legacy info requirements.\n\n"
                    "Quyền lợi\n"
                    "Legacy info benefits."
                ),
            },
            ensure_ascii=False,
        ),
    )

    provider = DummyProvider()
    raw_context, description, requirement, benefit, work_location, working_time, application_method = provider._prepare_job_context(job)

    assert description == "Legacy info description."
    assert requirement == "Legacy info requirements."
    assert benefit == "Legacy info benefits."
    assert work_location is None
    assert working_time is None
    assert application_method is None
    assert raw_context["info"].startswith("Mô tả công việc")


def test_llm_provider_handles_invalid_full_json_dump_without_crashing():
    job = SimpleNamespace(
        title="Markdown Title",
        location="Hanoi",
        raw_markdown=(
            "Mô tả công việc\n"
            "Markdown fallback description.\n\n"
            "Yêu cầu ứng viên\n"
            "Markdown fallback requirements.\n\n"
            "Quyền lợi\n"
            "Markdown fallback benefits."
        ),
        full_json_dump="not-json",
    )

    provider = DummyProvider()
    raw_context, description, requirement, benefit, work_location, working_time, application_method = provider._prepare_job_context(job)

    assert description == "Markdown fallback description."
    assert requirement == "Markdown fallback requirements."
    assert benefit == "Markdown fallback benefits."
    assert raw_context["info"].startswith("Mô tả công việc")
    assert work_location is None
    assert working_time is None
    assert application_method is None


def test_llm_prompt_includes_benefit_and_optional_topcv_context():
    prompt_template = """
    **TITLE:** {{ title }}
    **DESCRIPTION:** {{ description }}
    **REQUIREMENT:** {{ requirement }}
    **BENEFIT:** {{ benefit }}
    {% if work_location %}**WORK LOCATION:** {{ work_location }}{% endif %}
    {% if working_time %}**WORKING TIME:** {{ working_time }}{% endif %}
    {% if application_method %}**APPLICATION METHOD:** {{ application_method }}{% endif %}
    """
    prompt = _build_prompt(
        prompt_template,
        SimpleNamespace(title="Raw Title", company="TopCV", location="Hanoi"),
        {"salary": "Negotiable", "experience": "2 years"},
        "Structured description.",
        "Structured requirements.",
        "Structured benefits.",
        work_location="HÃ  Ná»™i",
        working_time="Mon-Fri",
        application_method="Apply online",
    )

    assert "Structured description." in prompt
    assert "Structured requirements." in prompt
    assert "Structured benefits." in prompt
    assert "WORK LOCATION" in prompt
    assert "HÃ  Ná»™i" in prompt
    assert "WORKING TIME" in prompt
    assert "Mon-Fri" in prompt
    assert "APPLICATION METHOD" in prompt
    assert "Apply online" in prompt


@pytest.mark.asyncio
async def test_process_jobs_deterministic_uses_structured_topcv_sections_without_llm(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/deterministic-structured",
        "title": "Raw Title",
        "location": "Unknown",
        "full_json_dump": {
            "title": "Raw Title",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "Legacy conflicting blob that should be ignored in deterministic mode.",
            "description": "Structured description from raw JSON.",
            "requirements": "Structured requirements from raw JSON.",
            "benefits": "Structured benefits from raw JSON.",
            "work_location": "HÃ  Ná»™i",
            "working_time": "Mon-Fri",
            "application_method": "Apply online",
        },
        "status": "pending",
    })

    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        side_effect=AssertionError("LLM should not be called in deterministic mode"),
    )
    mocker.patch(
        "src.internhunter.embeddings.embedder.Embedder.generate_embedding",
        side_effect=AssertionError("Embedding should not be called in deterministic mode"),
    )

    success_count, fail_count = await processor.process_jobs_deterministic(limit=10)

    assert success_count == 1
    assert fail_count == 0

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/deterministic-structured").first()
    assert raw_job is not None
    assert raw_job.status == "completed"
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.standardized_title == "Raw Title"
    assert raw_job.clean_job.company == "TopCV"
    assert raw_job.clean_job.description == "Structured description from raw JSON."
    assert raw_job.clean_job.requirement == "Structured requirements from raw JSON."
    assert raw_job.clean_job.benefit == "Structured benefits from raw JSON."
    assert list(raw_job.clean_job.cities) == ["HÃ  Ná»™i"]


@pytest.mark.asyncio
async def test_process_jobs_deterministic_uses_legacy_info_when_structured_fields_missing(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/deterministic-legacy-info",
        "title": "Legacy Title",
        "location": "Hanoi",
        "raw_markdown": "Fallback markdown that is not needed when info exists.",
        "full_json_dump": {
            "title": "Legacy Title",
            "company": "TopCV",
            "location": "Hanoi",
            "info": (
                    "Mô tả công việc\n"
                    "Legacy info description.\n\n"
                    "Yêu cầu ứng viên\n"
                    "Legacy info requirements.\n\n"
                    "Quyền lợi\n"
                    "Legacy info benefits."
            ),
        },
        "status": "pending",
    })

    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        side_effect=AssertionError("LLM should not be called in deterministic mode"),
    )
    mocker.patch(
        "src.internhunter.embeddings.embedder.Embedder.generate_embedding",
        side_effect=AssertionError("Embedding should not be called in deterministic mode"),
    )

    success_count, fail_count = await processor.process_jobs_deterministic(limit=10)

    assert success_count == 1
    assert fail_count == 0

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/deterministic-legacy-info").first()
    assert raw_job is not None
    assert raw_job.status == "completed"
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.description == "Legacy info description."
    assert raw_job.clean_job.requirement == "Legacy info requirements."
    assert raw_job.clean_job.benefit == "Legacy info benefits."
    assert list(raw_job.clean_job.cities) == ["Hanoi"]


@pytest.mark.asyncio
async def test_process_jobs_deterministic_handles_invalid_full_json_dump_without_crashing(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/deterministic-invalid-json",
        "title": "Invalid JSON Title",
        "location": "Hanoi",
        "raw_markdown": (
                    "Mô tả công việc\n"
                    "Markdown fallback description.\n\n"
                    "Yêu cầu ứng viên\n"
                    "Markdown fallback requirements.\n\n"
                    "Quyền lợi\n"
                    "Markdown fallback benefits."
        ),
        "full_json_dump": "not-json",
        "status": "pending",
    })

    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        side_effect=AssertionError("LLM should not be called in deterministic mode"),
    )
    mocker.patch(
        "src.internhunter.embeddings.embedder.Embedder.generate_embedding",
        side_effect=AssertionError("Embedding should not be called in deterministic mode"),
    )

    success_count, fail_count = await processor.process_jobs_deterministic(limit=10)

    assert success_count == 1
    assert fail_count == 0

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/deterministic-invalid-json").first()
    assert raw_job is not None
    assert raw_job.status == "completed"
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.description == "Markdown fallback description."
    assert raw_job.clean_job.requirement == "Markdown fallback requirements."
    assert raw_job.clean_job.benefit == "Markdown fallback benefits."


def test_build_validation_text_includes_css_success_fields():
    job = SimpleNamespace(
        title="Data Scientist",
        company="TopCV",
        location="Hanoi",
        raw_markdown=None,
        full_json_dump={
            "title": "Data Scientist",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "This is a detailed job info section with responsibilities and requirements.",
            "metadata": {"blocked_reason": "blocked_or_empty_content"},
        },
    )

    text = build_validation_text(job)

    assert "Data Scientist" in text
    assert "TopCV" in text
    assert "Hanoi" in text
    assert "detailed job info section" in text
    assert "blocked_or_empty_content" not in text


def test_build_validation_text_uses_raw_markdown_for_raw_fallback():
    job = SimpleNamespace(
        title="Unknown (RAW)",
        company="Unknown (RAW)",
        location="Unknown",
        raw_markdown="This is a raw markdown job description with enough detail to validate.",
        full_json_dump={
            "error": "CSS extraction failed",
            "is_blocked": False,
            "blocked_reason": "empty_or_unparseable_css_content",
        },
    )

    text = build_validation_text(job)

    assert "This is a raw markdown job description" in text
    assert "Unknown (RAW)" in text
    assert "empty_or_unparseable_css_content" not in text


def test_build_validation_text_ignores_blocked_metadata_only_payload():
    job = SimpleNamespace(
        title=None,
        company=None,
        location=None,
        raw_markdown=None,
        full_json_dump={
            "error": "CSS extraction failed",
            "is_blocked": True,
            "blocked_reason": "blocked_or_empty_content",
        },
    )

    text = build_validation_text(job)

    assert text == ""


@pytest.mark.asyncio
async def test_process_jobs_prefers_structured_topcv_sections_over_conflicting_info(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/structured-topcv",
        "title": "Raw Title",
        "location": "Unknown",
        "raw_markdown": "Legacy markdown that should not be required when structured fields exist.",
        "full_json_dump": {
            "title": "Raw Title",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "Legacy conflicting blob that should be de-prioritized.",
            "description": "Structured description from raw JSON.",
            "requirements": "Structured requirements from raw JSON.",
            "benefits": "Structured benefits from raw JSON.",
            "work_location": "HÃ  Ná»™i",
            "working_time": "Mon-Fri",
            "application_method": "Apply online",
        },
        "status": "pending",
    })

    captured_job = {}

    mocker.patch.object(JobValidator, "is_valid", return_value=(True, "LLM ok"))

    def _capture_and_return_processed(job):
        captured_job["job"] = job
        return ProcessedJob(
            standardized_title="Software Engineer Test",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="Structured description from LLM",
            requirement="Structured requirements from LLM",
            benefit="Structured benefits from LLM",
        )

    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        side_effect=_capture_and_return_processed,
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10)

    assert success_count == 1
    assert fail_count == 0

    routed_job = captured_job["job"]
    normalized_payload = json.loads(routed_job.full_json_dump)
    assert normalized_payload["info"].startswith("Mô tả công việc")
    assert "Legacy conflicting blob" not in normalized_payload["info"]
    assert normalized_payload["description"] == "Structured description from raw JSON."
    assert normalized_payload["requirements"] == "Structured requirements from raw JSON."
    assert normalized_payload["benefits"] == "Structured benefits from raw JSON."
    assert normalized_payload["work_location"] == "HÃ  Ná»™i"
    assert normalized_payload["working_time"] == "Mon-Fri"
    assert normalized_payload["application_method"] == "Apply online"
    assert routed_job.location == "HÃ  Ná»™i"

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/structured-topcv").first()
    assert raw_job.status == "completed"
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.company == "TopCV"
    assert raw_job.clean_job.description == "Structured description from LLM"
    assert raw_job.clean_job.requirement == "Structured requirements from LLM"
    assert raw_job.clean_job.benefit == "Structured benefits from LLM"


@pytest.mark.asyncio
async def test_process_jobs_with_invalid_full_json_dump_still_completes(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/invalid-json",
        "title": "Raw Title",
        "location": "Hanoi",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "full_json_dump": "not-json",
        "status": "pending",
    })

    mocker.patch.object(JobValidator, "is_valid", return_value=(True, "LLM ok"))
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="Software Engineer Test",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python", "FastAPI"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="A realistic cleaned job description for testing.",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10)

    assert success_count == 1
    assert fail_count == 0

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/invalid-json").first()
    assert raw_job.status == "completed"
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.description == "A realistic cleaned job description for testing."
    assert raw_job.clean_job.requirement == "Python, APIs, testing"
    assert raw_job.clean_job.benefit == "Flexible work"

@pytest.mark.asyncio
async def test_process_jobs_success(test_db_session, repo, processor, mocker):
    # 1. Setup: Insert a pending raw job
    repo.save_raw_job({
        "url": "https://example.com/job/process-me",
        "title": "Raw Title",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10, # Pass heuristic
        "status": "pending"
    })
    
    # Mock the Embedder since we don't want to make real API calls for embeddings
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1]*768)
    
    # Mock validator to pass
    mocker.patch("src.internhunter.extraction.validator.JobValidator.is_valid", return_value=(True, ""))

    # Mock the LLM routing/extraction step so this stays a unit test.
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="Software Engineer Test",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python", "FastAPI"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="A realistic cleaned job description for testing.",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )

    # 2. Act: Run processing
    success_count, fail_count = await processor.process_jobs(limit=10)
    
    # 3. Assert
    assert success_count == 1
    assert fail_count == 0
    
    # Verify the job status was updated
    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/process-me").first()
    assert raw_job.status == "completed"
    
    # Verify the clean job was created and mapped correctly from the LLM Mock
    clean_job = raw_job.clean_job
    assert clean_job is not None
    assert clean_job.standardized_title == "Software Engineer Test"
    assert clean_job.job_level == "Mid"
    assert "Python" in clean_job.tech_stack


@pytest.mark.asyncio
async def test_process_jobs_default_mode_uses_llm_validation(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/default-validation",
        "title": "Data Scientist",
        "company": "TopCV",
        "location": "Hanoi",
        "full_json_dump": {
            "title": "Data Scientist",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "This job description contains enough detail and job-like keywords to pass heuristics.",
            "requirement": "Python, SQL",
            "benefit": "Flexible work",
        },
        "status": "pending",
    })

    llm_validate = mocker.patch.object(JobValidator, "validate_with_llm", return_value=(True, "LLM ok"))
    mocker.patch.object(JobValidator, "heuristic_check", return_value=True)
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="Software Engineer Test",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python", "FastAPI"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="A realistic cleaned job description for testing.",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10)

    assert llm_validate.called
    assert success_count == 1
    assert fail_count == 0


@pytest.mark.asyncio
async def test_process_jobs_skip_llm_validation_bypasses_llm_validation(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/skip-validation",
        "title": "Data Scientist",
        "company": "TopCV",
        "location": "Hanoi",
        "full_json_dump": {
            "title": "Data Scientist",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "This job description contains enough detail and job-like keywords to pass heuristics.",
            "requirement": "Python, SQL",
            "benefit": "Flexible work",
        },
        "status": "pending",
    })

    mocker.patch.object(JobValidator, "heuristic_check", return_value=True)
    mocker.patch.object(JobValidator, "validate_with_llm", side_effect=AssertionError("LLM validation should be skipped"))
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="Software Engineer Test",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python", "FastAPI"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="A realistic cleaned job description for testing.",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10, skip_llm_validation=True)

    assert success_count == 1
    assert fail_count == 0


@pytest.mark.asyncio
async def test_process_jobs_skip_llm_validation_does_not_instantiate_validator(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/skip-validation-no-validator",
        "title": "Data Scientist",
        "company": "TopCV",
        "location": "Hanoi",
        "full_json_dump": {
            "title": "Data Scientist",
            "company": "TopCV",
            "location": "Hanoi",
            "info": "This job description contains enough detail and job-like keywords to pass heuristics.",
            "requirement": "Python, SQL",
            "benefit": "Flexible work",
        },
        "status": "pending",
    })

    mocker.patch.object(JobValidator, "__init__", side_effect=AssertionError("Validator should not be instantiated when validation is skipped"))
    mocker.patch.object(JobValidator, "heuristic_check", return_value=True)
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="Data Scientist",
            job_level="Junior",
            is_internship=False,
            cities=["Hanoi"],
            experience=1.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python"],
            technical_competencies=["Build Models"],
            domain_knowledge=["ML"],
            description="Structured description",
            requirement="Structured requirements",
            benefit="Structured benefits",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10, skip_llm_validation=True)

    assert success_count == 1
    assert fail_count == 0


@pytest.mark.asyncio
async def test_process_jobs_skip_llm_validation_still_fails_heuristics(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/skip-validation-fail",
        "title": "Short",
        "company": "Tiny Co",
        "location": "VN",
        "raw_markdown": "Too short",
        "status": "pending",
    })

    mocker.patch.object(JobValidator, "heuristic_check", return_value=False)
    mocker.patch.object(JobValidator, "validate_with_llm", side_effect=AssertionError("LLM validation should not be called on heuristic failure"))

    success_count, fail_count = await processor.process_jobs(limit=10, skip_llm_validation=True)

    assert success_count == 0
    assert fail_count == 1

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/skip-validation-fail").first()
    assert raw_job.status == "failed"

    audit_row = get_latest_audit_row(test_db_session)
    assert audit_row is not None
    assert audit_row.error_type == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_process_jobs_saves_fixture_backed_processed_job(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/fixture-backed",
        "title": "Raw Title",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "status": "pending",
    })

    structured_fixture = load_processed_job_fixture("normal_job")

    mocker.patch("src.internhunter.extraction.validator.JobValidator.is_valid", return_value=(True, ""))
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=structured_fixture,
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=10)

    assert success_count == 1
    assert fail_count == 0

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/fixture-backed").first()
    assert raw_job.status == "completed"

    clean_job = raw_job.clean_job
    assert clean_job is not None
    assert clean_job.standardized_title == structured_fixture.standardized_title
    assert clean_job.description == structured_fixture.description
    assert list(clean_job.cities) == structured_fixture.cities
    assert list(clean_job.tech_stack) == structured_fixture.tech_stack
    assert list(clean_job.domain_knowledge) == structured_fixture.domain_knowledge

@pytest.mark.asyncio
async def test_process_jobs_validation_fails(test_db_session, repo, processor, mocker):
    # 1. Setup
    repo.save_raw_job({
        "url": "https://example.com/job/bad",
        "raw_markdown": "Too short",
        "status": "pending"
    })
    
    # Force validator to fail
    validator_reason = "Heuristic check failed: text too short or lacks job keywords."
    mocker.patch("src.internhunter.extraction.validator.JobValidator.is_valid", return_value=(False, validator_reason))
    
    # 2. Act
    success, fail = await processor.process_jobs(limit=10)
    
    # 3. Assert
    assert success == 0
    assert fail == 1 # Validation fails count as processing errors (status='failed')
    
    # Wait, the processor code marks validation failures as 'invalid'. Let's check.
    # Ah, if we look at job_processor.py:
    # if not is_valid: ... repo.update_job_status(job.id, "invalid") -> wait, the actual code says "failed". Let's check status.
    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/bad").first()
    assert raw_job.status == "failed"

    audit_row = get_latest_audit_row(test_db_session)
    assert audit_row is not None
    assert audit_row.error_type == "VALIDATION_FAILED"
    assert validator_reason in audit_row.error_message


@pytest.mark.asyncio
async def test_process_jobs_llm_incomplete_failure_is_audited(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/llm-incomplete",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "status": "pending",
    })

    mocker.patch("src.internhunter.extraction.validator.JobValidator.is_valid", return_value=(True, ""))
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        return_value=ProcessedJob(
            standardized_title="",
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description="",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success, fail = await processor.process_jobs(limit=10)

    assert success == 0
    assert fail == 1

    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/llm-incomplete").first()
    assert raw_job.status == "failed"

    audit_row = get_latest_audit_row(test_db_session)
    assert audit_row is not None
    assert audit_row.error_type == "LLM_INCOMPLETE"
    assert "Missing critical fields (title/description) in LLM output" in audit_row.error_message


@pytest.mark.asyncio
async def test_process_jobs_prioritizes_refreshed_current_run_jobs(test_db_session, repo, processor, mocker):
    repo.save_raw_job({
        "url": "https://example.com/job/older-pending-process",
        "crawl_run_id": "run-old",
        "title": "Older Pending Process",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "status": "pending",
    })
    repo.save_raw_job({
        "url": "https://example.com/job/current-run-process",
        "crawl_run_id": "run-current",
        "title": "Current Run Process",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "status": "pending",
    })
    repo.save_raw_job({
        "url": "https://example.com/job/current-run-process",
        "crawl_run_id": "run-current",
        "title": "Current Run Process Refreshed",
        "raw_markdown": "This is a dummy job description containing over 300 characters. " * 10,
        "status": "pending",
        "extraction_method": "raw",
    })

    mocker.patch("src.internhunter.extraction.validator.JobValidator.is_valid", return_value=(True, ""))
    mocker.patch(
        "src.internhunter.extraction.job_processor.llm_router.process_with_fallback",
        side_effect=lambda job: ProcessedJob(
            standardized_title=job.title,
            job_level="Mid",
            is_internship=False,
            cities=["Hanoi"],
            experience=2.0,
            min_gpa=None,
            english_requirement=None,
            salary_min=None,
            salary_max=None,
            currency="VND",
            is_salary_negotiable=False,
            tech_stack=["Python"],
            technical_competencies=["Build APIs"],
            domain_knowledge=["Web Development"],
            description=f"Processed {job.title}",
            requirement="Python, APIs, testing",
            benefit="Flexible work",
        ),
    )
    mocker.patch("src.internhunter.embeddings.embedder.Embedder.generate_embedding", return_value=[0.1] * 768)

    success_count, fail_count = await processor.process_jobs(limit=1, crawl_run_id="run-current")

    assert success_count == 1
    assert fail_count == 0

    current_run_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/current-run-process").first()
    older_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/older-pending-process").first()

    assert current_run_job.status == "completed"
    assert older_job.status == "pending"

