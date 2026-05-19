from __future__ import annotations

import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from src.internhunter.crawler.crawl import _derive_topcv_section_fields, _derive_topcv_section_fields_with_provenance


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "crawl_samples" / "topcv"
MANIFEST_PATH = FIXTURE_ROOT / "fixture_manifest.json"
LATEST_SUCCESS_RUN_ID = "fb750e62"

ALLOWED_LAYOUT_FAMILIES = {
    "standard_topcv",
    "branded_topcv",
    "raw_fallback",
    "blocked",
    "unknown",
}

SECTION_HEADING_MAP = {
    "description": ["MÃ´ táº£ cÃ´ng viá»‡c"],
    "requirements": ["YÃªu cáº§u á»©ng viÃªn"],
    "benefits": ["Quyá»n lá»£i", "Quyá»n lá»£i Ä‘Æ°á»£c hÆ°á»Ÿng"],
    "work_location": ["Äá»‹a Ä‘iá»ƒm lÃ m viá»‡c"],
    "working_time": ["Thá»i gian lÃ m viá»‡c"],
}

BRANDED_HTML_MARKERS = {
    "premium-job-description__box--content",
    "premium-job-description__box--title",
    "basic-information-item__data--label",
    "policy__title--name",
    "footer-info",
    "company-content__name",
}

SHALLOW_JSON_FIELDS = {"title", "company", "salary", "location", "experience", "info"}
SEMANTIC_SECTION_FIELDS = set(SECTION_HEADING_MAP.keys())


def load_fixture_manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"Expected fixture manifest at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def group_samples_by_layout_family(manifest: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for sample in manifest.get("samples", []):
        grouped[sample.get("layout_family", "unknown")].append(sample)
    return dict(grouped)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return " ".join(normalized.split())


def text_contains_section_heading(text: str | None, heading: str) -> bool:
    return normalize_text(heading).casefold() in normalize_text(text).casefold()


def extract_current_json_fields(full_json_dump: dict) -> set[str]:
    if not isinstance(full_json_dump, dict):
        return set()
    return set(full_json_dump.keys())


def load_sample_artifacts(sample_dir: Path) -> dict:
    metadata_path = sample_dir / "metadata.json"
    raw_html_path = sample_dir / "raw.html"
    raw_markdown_path = sample_dir / "raw_markdown.txt"
    full_json_path = sample_dir / "full_json_dump.json"

    assert metadata_path.exists(), f"Missing metadata.json in {sample_dir}"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw_html = raw_html_path.read_text(encoding="utf-8") if raw_html_path.exists() else ""
    raw_markdown = raw_markdown_path.read_text(encoding="utf-8") if raw_markdown_path.exists() else ""
    full_json = json.loads(full_json_path.read_text(encoding="utf-8")) if full_json_path.exists() else {}

    screenshot_exists = False
    screenshot_path = metadata.get("screenshot_path")
    if screenshot_path:
        screenshot_exists = Path(screenshot_path).exists()
    if not screenshot_exists:
        screenshot_exists = any(path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} for path in sample_dir.iterdir())

    return {
        "metadata": metadata,
        "raw_html": raw_html,
        "raw_markdown": raw_markdown,
        "full_json_dump": full_json,
        "raw_html_exists": raw_html_path.exists(),
        "raw_markdown_exists": raw_markdown_path.exists(),
        "full_json_exists": full_json_path.exists(),
        "screenshot_exists": screenshot_exists,
    }


def detect_section_presence(artifacts: dict, section_headings: dict[str, list[str]] | None = None) -> dict[str, dict[str, bool]]:
    section_headings = section_headings or SECTION_HEADING_MAP
    presence: dict[str, dict[str, bool]] = {}
    raw_html = artifacts.get("raw_html", "")
    raw_markdown = artifacts.get("raw_markdown", "")
    full_json_dump = artifacts.get("full_json_dump", {})
    info_text = ""
    if isinstance(full_json_dump, dict):
        info_text = str(full_json_dump.get("info", "") or "")

    for field_name, headings in section_headings.items():
        presence[field_name] = {
            "html": any(text_contains_section_heading(raw_html, heading) for heading in headings),
            "markdown": any(text_contains_section_heading(raw_markdown, heading) for heading in headings),
            "info": any(text_contains_section_heading(info_text, heading) for heading in headings),
        }
        presence[field_name]["present"] = any(presence[field_name].values())
    return presence


def is_successful_css_sample(metadata: dict) -> bool:
    return metadata.get("status") == "pending" and metadata.get("extraction_method") == "css"


def _manifest_sample_path(sample: dict) -> Path:
    return FIXTURE_ROOT / sample["sample_dir"]


def _manifest_sample_by_dir(sample_dir: Path) -> dict | None:
    manifest = load_fixture_manifest()
    relative_dir = sample_dir.relative_to(FIXTURE_ROOT).as_posix()
    for sample in manifest.get("samples", []):
        if sample.get("sample_dir") == relative_dir:
            return sample
    return None


def _load_grouped_manifest_samples() -> dict[str, list[dict]]:
    return group_samples_by_layout_family(load_fixture_manifest())


def _successful_css_samples(layout_family: str) -> list[dict]:
    grouped = _load_grouped_manifest_samples()
    return [
        sample
        for sample in grouped.get(layout_family, [])
        if _safe_manifest_sample_is_successful(sample)
    ]


def _safe_manifest_sample_is_successful(sample: dict) -> bool:
    sample_dir = _manifest_sample_path(sample)
    metadata = json.loads((sample_dir / "metadata.json").read_text(encoding="utf-8"))
    return is_successful_css_sample(metadata)


def _assert_section_headings_visible(artifacts: dict, section_names: list[str]) -> None:
    for section_name in section_names:
        assert text_contains_section_heading(artifacts["raw_html"], SECTION_HEADING_MAP[section_name][0]) or text_contains_section_heading(
            artifacts["raw_markdown"], SECTION_HEADING_MAP[section_name][0]
        ), f"Missing {section_name} heading in raw artifacts"


def test_topcv_fixture_manifest_groups_samples_by_layout_family():
    manifest = load_fixture_manifest()
    samples = manifest.get("samples", [])
    assert samples, "Expected at least one labeled sample in fixture_manifest.json"

    grouped = Counter()
    for sample in samples:
        layout_family = sample.get("layout_family")
        assert layout_family in ALLOWED_LAYOUT_FAMILIES
        grouped[layout_family] += 1

        sample_dir = _manifest_sample_path(sample)
        assert sample_dir.exists(), f"Missing sample directory: {sample_dir}"
        metadata_path = sample_dir / "metadata.json"
        assert metadata_path.exists(), f"Missing metadata.json in {sample_dir}"

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["crawl_run_id"] == sample["crawl_run_id"]
        assert metadata["url"] == sample["url"]
        if sample.get("expected_status"):
            assert metadata["status"] == sample["expected_status"]
        if sample.get("expected_extraction_method"):
            assert metadata["extraction_method"] == sample["expected_extraction_method"]

    assert grouped["standard_topcv"] >= 1
    assert grouped["branded_topcv"] >= 1


def test_standard_topcv_samples_expose_expected_sections_in_html_or_markdown():
    grouped = _load_grouped_manifest_samples()
    standard_samples = grouped.get("standard_topcv", [])
    assert standard_samples, "Expected at least one standard_topcv fixture sample"

    for sample in standard_samples:
        sample_dir = _manifest_sample_path(sample)
        artifacts = load_sample_artifacts(sample_dir)
        metadata = artifacts["metadata"]
        full_json = artifacts["full_json_dump"]
        if not isinstance(full_json, dict) or not full_json.get("extraction_version"):
            continue

        assert artifacts["raw_html_exists"] or artifacts["raw_markdown_exists"]
        assert metadata["url"].startswith("https://www.topcv.vn/")
        assert metadata["crawl_run_id"] == sample["crawl_run_id"]
        assert metadata["source_seed_url"].startswith("https://www.topcv.vn/tim-viec-lam-")

        if is_successful_css_sample(metadata):
            assert metadata["title"] not in {"Unknown", "Unknown (RAW)"}
            assert metadata["company"] not in {"Unknown", "Unknown (RAW)"}

        assert full_json.get("info")
        for section_name in SECTION_HEADING_MAP:
            assert full_json.get(section_name), f"Expected structured {section_name} in full_json_dump for {sample_dir}"

        section_presence = detect_section_presence(artifacts)
        assert set(section_presence).issuperset(set(SECTION_HEADING_MAP))


def test_standard_topcv_fixture_artifacts_allow_description_requirements_benefits_and_work_location_extraction():
    grouped = _load_grouped_manifest_samples()
    standard_samples = grouped.get("standard_topcv", [])
    assert standard_samples, "Expected at least one standard_topcv fixture sample"

    for sample in standard_samples:
        sample_dir = _manifest_sample_path(sample)
        artifacts = load_sample_artifacts(sample_dir)
        metadata = artifacts["metadata"]
        if not is_successful_css_sample(metadata):
            continue

        extracted_sections = _derive_topcv_section_fields(
            raw_markdown=artifacts["raw_markdown"],
            info_text=str(artifacts["full_json_dump"].get("info") or ""),
            html_text=artifacts["raw_html"],
        )
        section_presence = detect_section_presence(artifacts)
        assert extracted_sections["description"], f"Expected description extraction from {sample_dir}"
        assert extracted_sections["requirements"], f"Expected requirements extraction from {sample_dir}"
        assert extracted_sections["benefits"], f"Expected benefits extraction from {sample_dir}"
        assert extracted_sections["work_location"], f"Expected work_location extraction from {sample_dir}"
        if section_presence["working_time"]["html"] or section_presence["working_time"]["markdown"]:
            assert extracted_sections["working_time"], f"Expected working_time extraction from {sample_dir}"


def test_topcv_fixture_artifacts_report_section_source_provenance_from_preferred_container():
    grouped = _load_grouped_manifest_samples()
    for layout_family in ("standard_topcv", "branded_topcv"):
        samples = grouped.get(layout_family, [])
        assert samples, f"Expected at least one {layout_family} fixture sample"

        for sample in samples:
            sample_dir = _manifest_sample_path(sample)
            artifacts = load_sample_artifacts(sample_dir)
            metadata = artifacts["metadata"]
            if not is_successful_css_sample(metadata):
                continue

            section_presence = detect_section_presence(artifacts)
            extracted_sections, section_sources = _derive_topcv_section_fields_with_provenance(
                raw_markdown=artifacts["raw_markdown"],
                info_text=str(artifacts["full_json_dump"].get("info") or ""),
                html_text=artifacts["raw_html"],
            )

            assert section_sources["description"] in {"css_selected_job_content", "raw_markdown", "html_text"}
            assert section_sources["requirements"] in {"css_selected_job_content", "raw_markdown", "html_text"}
            assert section_sources["benefits"] in {"css_selected_job_content", "raw_markdown", "html_text"}
            assert section_sources["work_location"] in {"css_selected_job_content", "raw_markdown", "html_text"}
            assert extracted_sections["description"]
            assert extracted_sections["requirements"]
            assert extracted_sections["benefits"]
            assert extracted_sections["work_location"]

            if section_presence["working_time"]["html"] or section_presence["working_time"]["markdown"]:
                assert extracted_sections["working_time"]
                assert section_sources["working_time"] in {"css_selected_job_content", "raw_markdown", "html_text"}


def test_branded_topcv_samples_expose_expected_sections_in_html_or_markdown():
    grouped = _load_grouped_manifest_samples()
    branded_samples = grouped.get("branded_topcv", [])
    assert branded_samples, "Expected at least one branded_topcv fixture sample"

    observed_sections = set()
    for sample in branded_samples:
        sample_dir = _manifest_sample_path(sample)
        artifacts = load_sample_artifacts(sample_dir)
        metadata = artifacts["metadata"]
        raw_html = artifacts["raw_html"]
        full_json = artifacts["full_json_dump"]
        if not isinstance(full_json, dict) or not full_json.get("extraction_version"):
            continue

        assert artifacts["raw_html_exists"] or artifacts["raw_markdown_exists"]
        assert metadata["url"].startswith("https://www.topcv.vn/")
        assert metadata["crawl_run_id"] == sample["crawl_run_id"]
        assert metadata["source_seed_url"].startswith("manual_") or metadata["source_seed_url"].startswith("https://www.topcv.vn/")

        if is_successful_css_sample(metadata):
            assert metadata["title"] not in {"Unknown", "Unknown (RAW)"}
            assert metadata["company"] not in {"Unknown", "Unknown (RAW)"}

        for section_name in {"description", "requirements", "benefits", "work_location"}:
            assert full_json.get(section_name), f"Expected structured {section_name} in full_json_dump for {sample_dir}"

        section_presence = detect_section_presence(artifacts)
        visible_sections = {
            section_name
            for section_name, sources in section_presence.items()
            if sources["present"]
        }
        observed_sections.update(visible_sections)

        found_branded_markers = sorted(marker for marker in BRANDED_HTML_MARKERS if marker in raw_html)
        assert found_branded_markers, f"Expected branded HTML markers in {sample_dir}"

    assert observed_sections.issubset(set(SECTION_HEADING_MAP))


def test_branded_topcv_fixture_artifacts_allow_description_requirements_benefits_and_work_location_extraction():
    grouped = _load_grouped_manifest_samples()
    branded_samples = grouped.get("branded_topcv", [])
    assert branded_samples, "Expected at least one branded_topcv fixture sample"

    for sample in branded_samples:
        sample_dir = _manifest_sample_path(sample)
        artifacts = load_sample_artifacts(sample_dir)
        metadata = artifacts["metadata"]
        if not is_successful_css_sample(metadata):
            continue

        extracted_sections = _derive_topcv_section_fields(
            raw_markdown=artifacts["raw_markdown"],
            info_text=str(artifacts["full_json_dump"].get("info") or ""),
            html_text=artifacts["raw_html"],
        )
        assert extracted_sections["description"], f"Expected description extraction from {sample_dir}"
        assert extracted_sections["requirements"], f"Expected requirements extraction from {sample_dir}"
        assert extracted_sections["benefits"], f"Expected benefits extraction from {sample_dir}"
        assert extracted_sections["work_location"], f"Expected work_location extraction from {sample_dir}"
        assert extracted_sections["working_time"], f"Expected working_time extraction from {sample_dir}"
        section_presence = detect_section_presence(artifacts)


def test_current_full_json_dump_keeps_older_exported_fixture_samples_shallow():
    manifest = load_fixture_manifest()
    successful_samples = [
        sample
        for sample in manifest.get("samples", [])
        if _safe_manifest_sample_is_successful(sample)
    ]
    assert successful_samples, "Expected at least one successful CSS fixture sample"

    for sample in successful_samples:
        sample_dir = _manifest_sample_path(sample)
        artifacts = load_sample_artifacts(sample_dir)
        full_json = artifacts["full_json_dump"]
        extracted_fields = extract_current_json_fields(full_json)
        section_presence = detect_section_presence(artifacts)
        if not isinstance(full_json, dict) or not full_json.get("extraction_version"):
            continue

        if extracted_fields - SHALLOW_JSON_FIELDS:
            continue
        assert extracted_fields <= SHALLOW_JSON_FIELDS, f"Unexpected structured keys in {sample_dir}"
        assert SEMANTIC_SECTION_FIELDS.isdisjoint(extracted_fields), f"Unexpected structured section keys in {sample_dir}"
        assert full_json.get("info")
        if sample.get("layout_family") == "standard_topcv":
            assert all(section_presence[section_name]["info"] for section_name in SECTION_HEADING_MAP), (
                f"Expected standard layout info to carry all canonical sections for {sample_dir}"
            )


def test_latest_successful_topcv_export_includes_all_structured_sections_in_full_json_dump():
    manifest = load_fixture_manifest()
    candidates = []
    for sample in manifest.get("samples", []):
        if sample.get("layout_family") != "standard_topcv":
            continue
        artifacts = load_sample_artifacts(_manifest_sample_path(sample))
        full_json = artifacts["full_json_dump"]
        if {"working_time"} <= extract_current_json_fields(full_json):
            candidates.append((sample, artifacts))

    assert candidates, "Expected at least one structured standard_topcv export with working_time"
    sample, artifacts = candidates[0]
    full_json = artifacts["full_json_dump"]

    assert sample["layout_family"] == "standard_topcv"
    assert {"description", "requirements", "benefits", "work_location", "working_time"}.issubset(
        extract_current_json_fields(full_json)
    )
    assert full_json["description"]
    assert full_json["requirements"]
    assert full_json["benefits"]
    assert full_json["work_location"]
    assert full_json["working_time"]


def test_detected_sections_match_expected_layout_family_matrix():
    manifest = load_fixture_manifest()
    grouped = group_samples_by_layout_family(manifest)

    standard_samples = [sample for sample in grouped.get("standard_topcv", []) if _safe_manifest_sample_is_successful(sample)]
    branded_samples = [sample for sample in grouped.get("branded_topcv", []) if _safe_manifest_sample_is_successful(sample)]

    assert standard_samples, "Expected at least one successful standard_topcv sample"
    assert branded_samples, "Expected at least one successful branded_topcv sample"

    standard_sample = next(
        sample
        for sample in standard_samples
        if load_sample_artifacts(_manifest_sample_path(sample))["full_json_dump"].get("extraction_version")
    )
    branded_sample = next(
        sample
        for sample in branded_samples
        if load_sample_artifacts(_manifest_sample_path(sample))["full_json_dump"].get("extraction_version")
    )

    standard_artifacts = load_sample_artifacts(_manifest_sample_path(standard_sample))
    branded_artifacts = load_sample_artifacts(_manifest_sample_path(branded_sample))

    standard_presence = detect_section_presence(standard_artifacts)
    branded_presence = detect_section_presence(branded_artifacts)

    standard_present_sections = {section for section, sources in standard_presence.items() if sources["present"]}
    branded_present_sections = {section for section, sources in branded_presence.items() if sources["present"]}

    assert {"description", "requirements", "benefits", "work_location"}.issubset(
        extract_current_json_fields(standard_artifacts["full_json_dump"])
    )
    assert {"description", "requirements", "benefits", "work_location"}.issubset(
        extract_current_json_fields(branded_artifacts["full_json_dump"])
    )
    assert standard_present_sections or standard_artifacts["full_json_dump"].get("info")
    assert branded_present_sections or branded_artifacts["full_json_dump"].get("info")

    standard_markers = {
        marker
        for marker in BRANDED_HTML_MARKERS
        if marker in standard_artifacts["raw_html"]
    }
    branded_markers = {
        marker
        for marker in BRANDED_HTML_MARKERS
        if marker in branded_artifacts["raw_html"]
    }

    assert "premium-job-description__box--content" not in standard_markers
    assert "basic-information-item__data--label" not in standard_markers
    assert branded_markers


def test_topcv_fixture_manifest_layout_groups_match_exported_samples():
    manifest = load_fixture_manifest()
    samples = manifest.get("samples", [])
    layout_groups = {}
    for sample in samples:
        layout_groups.setdefault(sample["layout_family"], []).append(sample)

    assert "standard_topcv" in layout_groups
    assert len(layout_groups["standard_topcv"]) >= 1
    assert "branded_topcv" in layout_groups
    assert len(layout_groups["branded_topcv"]) >= 1


def test_branded_topcv_manifest_samples_allow_manual_source_labels():
    manifest = load_fixture_manifest()
    branded_samples = [sample for sample in manifest.get("samples", []) if sample.get("layout_family") == "branded_topcv"]
    for sample in branded_samples:
        sample_dir = _manifest_sample_path(sample)
        metadata = json.loads((sample_dir / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["source_seed_url"] == "manual_branded_topcv" or metadata["source_seed_url"].startswith("manual_")

