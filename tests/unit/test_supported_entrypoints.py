import importlib.util


def test_supported_entrypoints_import():
    from src.internhunter.orchestration.ingestion_flow import job_ingestion_flow
    from src.run_pipeline import run_full_pipeline

    assert callable(run_full_pipeline)
    assert callable(job_ingestion_flow)


def test_removed_cli_entrypoints_are_absent():
    assert importlib.util.find_spec("src.main") is None
    assert importlib.util.find_spec("src.internhunter.orchestration.cli") is None
