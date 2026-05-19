import pytest
import src.run_pipeline as run_pipeline_module

from src.core.models.fetch_result import FetchOutcome, FetchStatus
from src.internhunter.orchestration.ingestion_flow import job_ingestion_flow as canonical_ingestion_flow
import src.internhunter.orchestration.ingestion_flow as ingestion_flow_module


def test_orchestration_imports_resolve():
    assert callable(canonical_ingestion_flow)


@pytest.mark.asyncio
async def test_job_ingestion_flow_limits_crawl_to_requested_job_count(mocker):
    captured = {
        "fetch_limit": None,
        "fetch_run_id": None,
        "crawl_count": None,
        "process_limit": None,
        "process_crawl_run_id": None,
        "force_recrawl": None,
        "crawl_force_recrawl": None,
        "skip_llm_validation": None,
    }

    async def fake_fetch_links_task(run_id, limit=None, force_recrawl=False):
        captured["fetch_run_id"] = run_id
        captured["fetch_limit"] = limit
        captured["force_recrawl"] = force_recrawl
        return FetchOutcome(
            status=FetchStatus.SUCCESS,
            links=[
                {"url": "https://example.com/job/1"},
                {"url": "https://example.com/job/2"},
                {"url": "https://example.com/job/3"},
                {"url": "https://example.com/job/4"},
            ],
            total_scraped=4,
            pages_scraped=1,
        )

    async def fake_crawl_jobs_task(links, run_id, force_recrawl=False):
        captured["crawl_count"] = len(links)
        captured["crawl_force_recrawl"] = force_recrawl
        return len(links), 0

    async def fake_process_jobs_task(limit, skip_llm_validation=False, crawl_run_id=None):
        captured["process_limit"] = limit
        captured["skip_llm_validation"] = skip_llm_validation
        captured["process_crawl_run_id"] = crawl_run_id
        return 3, 0

    class DummyRepo:
        def create_tables(self):
            return None

        def save_pipeline_run_summary(self, **kwargs):
            return None

    mocker.patch.object(ingestion_flow_module, "configure_logging", return_value=None)
    mocker.patch.object(ingestion_flow_module, "fetch_links_task", side_effect=fake_fetch_links_task)
    mocker.patch.object(ingestion_flow_module, "crawl_jobs_task", side_effect=fake_crawl_jobs_task)
    mocker.patch.object(ingestion_flow_module, "process_jobs_task", side_effect=fake_process_jobs_task)
    mocker.patch.object(ingestion_flow_module, "ETLRepository", return_value=DummyRepo())

    await canonical_ingestion_flow(limit=3, force_recrawl=True, skip_llm_validation=True)

    assert captured["fetch_limit"] == 3
    assert captured["force_recrawl"] is True
    assert captured["crawl_count"] == 3
    assert captured["crawl_force_recrawl"] is True
    assert captured["process_limit"] == 3
    assert captured["skip_llm_validation"] is True
    assert captured["process_crawl_run_id"] == captured["fetch_run_id"]


@pytest.mark.asyncio
async def test_job_ingestion_flow_crawl_only_skips_processing(mocker):
    captured = {
        "fetch_called": False,
        "crawl_called": False,
        "process_called": False,
        "crawl_run_id": None,
    }

    async def fake_fetch_links_task(run_id, limit=None, force_recrawl=False):
        captured["fetch_called"] = True
        return FetchOutcome(
            status=FetchStatus.SUCCESS,
            links=[
                {"url": "https://example.com/job/1"},
                {"url": "https://example.com/job/2"},
            ],
            total_scraped=2,
            pages_scraped=1,
        )

    async def fake_crawl_jobs_task(links, run_id, force_recrawl=False):
        captured["crawl_called"] = True
        captured["crawl_run_id"] = run_id
        return len(links), 0

    async def fake_process_jobs_task(limit, skip_llm_validation=False, crawl_run_id=None):
        captured["process_called"] = True
        return 0, 0

    class DummyRepo:
        def create_tables(self):
            return None

        def save_pipeline_run_summary(self, **kwargs):
            return None

    mocker.patch.object(ingestion_flow_module, "configure_logging", return_value=None)
    mocker.patch.object(ingestion_flow_module, "fetch_links_task", side_effect=fake_fetch_links_task)
    mocker.patch.object(ingestion_flow_module, "crawl_jobs_task", side_effect=fake_crawl_jobs_task)
    mocker.patch.object(ingestion_flow_module, "process_jobs_task", side_effect=fake_process_jobs_task)
    mocker.patch.object(ingestion_flow_module, "ETLRepository", return_value=DummyRepo())

    await canonical_ingestion_flow(limit=2, force_recrawl=True, skip_llm_validation=True, crawl_only=True)

    assert captured["fetch_called"] is True
    assert captured["crawl_called"] is True
    assert captured["process_called"] is False
    assert captured["crawl_run_id"] is not None


@pytest.mark.asyncio
async def test_job_ingestion_flow_skips_when_no_new_links_after_dedup(mocker):
    captured = {"fetch_limit": None, "crawl_called": False, "process_called": False}

    async def fake_fetch_links_task(run_id, limit=None, force_recrawl=False):
        captured["fetch_limit"] = limit
        return FetchOutcome(
            status=FetchStatus.NO_NEW,
            links=[],
            total_scraped=4,
            pages_scraped=2,
        )

    async def fake_crawl_jobs_task(links, run_id, force_recrawl=False):
        captured["crawl_called"] = True
        return len(links), 0

    async def fake_process_jobs_task(limit, skip_llm_validation=False, crawl_run_id=None):
        captured["process_called"] = True
        return 0, 0

    class DummyRepo:
        def create_tables(self):
            return None

        def save_pipeline_run_summary(self, **kwargs):
            return None

    mocker.patch.object(ingestion_flow_module, "configure_logging", return_value=None)
    mocker.patch.object(ingestion_flow_module, "fetch_links_task", side_effect=fake_fetch_links_task)
    mocker.patch.object(ingestion_flow_module, "crawl_jobs_task", side_effect=fake_crawl_jobs_task)
    mocker.patch.object(ingestion_flow_module, "process_jobs_task", side_effect=fake_process_jobs_task)
    mocker.patch.object(ingestion_flow_module, "ETLRepository", return_value=DummyRepo())

    await canonical_ingestion_flow(limit=3)

    assert captured["fetch_limit"] == 3
    assert captured["crawl_called"] is False
    assert captured["process_called"] is False


def test_run_pipeline_defaults_to_skipping_llm_validation(mocker):
    captured = {}

    async def fake_job_ingestion_flow(limit, force_recrawl=False, skip_llm_validation=False, crawl_only=False):
        captured.update(
            {
                "limit": limit,
                "force_recrawl": force_recrawl,
                "skip_llm_validation": skip_llm_validation,
                "crawl_only": crawl_only,
            }
        )

    mocker.patch.object(run_pipeline_module, "job_ingestion_flow", side_effect=fake_job_ingestion_flow)

    exit_code = run_pipeline_module.main(["--limit", "2", "--force-recrawl"])

    assert exit_code == 0
    assert captured == {
        "limit": 2,
        "force_recrawl": True,
        "skip_llm_validation": True,
        "crawl_only": False,
    }


def test_run_pipeline_enable_llm_validation_opt_in_flag_enables_validation(mocker):
    captured = {}

    async def fake_job_ingestion_flow(limit, force_recrawl=False, skip_llm_validation=False, crawl_only=False):
        captured.update(
            {
                "limit": limit,
                "force_recrawl": force_recrawl,
                "skip_llm_validation": skip_llm_validation,
                "crawl_only": crawl_only,
            }
        )

    mocker.patch.object(run_pipeline_module, "job_ingestion_flow", side_effect=fake_job_ingestion_flow)

    exit_code = run_pipeline_module.main(["--enable-llm-validation"])

    assert exit_code == 0
    assert captured["skip_llm_validation"] is False


def test_run_pipeline_skip_llm_validation_compatibility_alias_keeps_validation_off(mocker):
    captured = {}

    async def fake_job_ingestion_flow(limit, force_recrawl=False, skip_llm_validation=False, crawl_only=False):
        captured.update(
            {
                "limit": limit,
                "force_recrawl": force_recrawl,
                "skip_llm_validation": skip_llm_validation,
                "crawl_only": crawl_only,
            }
        )

    mocker.patch.object(run_pipeline_module, "job_ingestion_flow", side_effect=fake_job_ingestion_flow)

    exit_code = run_pipeline_module.main(["--skip-llm-validation"])

    assert exit_code == 0
    assert captured["skip_llm_validation"] is True


@pytest.mark.asyncio
async def test_job_ingestion_flow_skips_when_fetch_links_fails(mocker):
    captured = {"crawl_called": False, "process_called": False}

    async def fake_fetch_links_task(run_id, limit=None, force_recrawl=False):
        return FetchOutcome(
            status=FetchStatus.NETWORK_FAIL,
            links=[],
            total_scraped=0,
            pages_scraped=0,
            error="network down",
        )

    async def fake_crawl_jobs_task(links, run_id, force_recrawl=False):
        captured["crawl_called"] = True
        return len(links), 0

    async def fake_process_jobs_task(limit, skip_llm_validation=False, crawl_run_id=None):
        captured["process_called"] = True
        return 0, 0

    class DummyRepo:
        def create_tables(self):
            return None

        def save_pipeline_run_summary(self, **kwargs):
            return None

    mocker.patch.object(ingestion_flow_module, "configure_logging", return_value=None)
    mocker.patch.object(ingestion_flow_module, "fetch_links_task", side_effect=fake_fetch_links_task)
    mocker.patch.object(ingestion_flow_module, "crawl_jobs_task", side_effect=fake_crawl_jobs_task)
    mocker.patch.object(ingestion_flow_module, "process_jobs_task", side_effect=fake_process_jobs_task)
    mocker.patch.object(ingestion_flow_module, "ETLRepository", return_value=DummyRepo())

    await canonical_ingestion_flow(limit=3)

    assert captured["crawl_called"] is False
    assert captured["process_called"] is False
