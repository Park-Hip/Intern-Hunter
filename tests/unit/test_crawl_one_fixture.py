from __future__ import annotations

import json

from src.scripts.crawl_one_fixture import _append_manifest_entry, _brand_from_url, _build_manifest_entry


def test_crawl_one_fixture_detects_brand_from_url():
    assert _brand_from_url(
        "https://www.topcv.vn/brand/vpbank/tuyen-dung/senior-data-scientist-ha-noi-ta174-j2158119.html"
    ) == "vpbank"
    assert _brand_from_url("https://www.topcv.vn/viec-lam/123.html") == "manual_fixture"


def test_crawl_one_fixture_builds_manifest_entry_for_branded_sample():
    entry = _build_manifest_entry(
        crawl_run_id="run-123",
        sample_dir="run-123/sample-dir",
        url="https://www.topcv.vn/brand/vpbank/tuyen-dung/example.html",
        layout_family="branded_topcv",
        expected_status="pending",
        expected_extraction_method="css",
        notes="manual branded_topcv fixture for vpbank",
    )

    assert entry == {
        "crawl_run_id": "run-123",
        "sample_dir": "run-123/sample-dir",
        "url": "https://www.topcv.vn/brand/vpbank/tuyen-dung/example.html",
        "layout_family": "branded_topcv",
        "expected_status": "pending",
        "expected_extraction_method": "css",
        "notes": "manual branded_topcv fixture for vpbank",
    }


def test_crawl_one_fixture_appends_manifest_entry(tmp_path):
    manifest_path = tmp_path / "fixture_manifest.json"
    entry = _build_manifest_entry(
        crawl_run_id="run-123",
        sample_dir="run-123/sample-dir",
        url="https://www.topcv.vn/brand/vpbank/tuyen-dung/example.html",
        layout_family="branded_topcv",
        expected_status="pending",
        expected_extraction_method="css",
        notes="manual branded_topcv fixture for vpbank",
    )

    _append_manifest_entry(manifest_path, entry)
    _append_manifest_entry(manifest_path, entry)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["samples"]) == 2
    assert manifest["samples"][0]["layout_family"] == "branded_topcv"
