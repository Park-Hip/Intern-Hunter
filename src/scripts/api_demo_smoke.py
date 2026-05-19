import argparse
import sys
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def _configure_stdio() -> None:
    """Make console output robust on Windows terminals with non-UTF-8 defaults."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                # Best effort only: the smoke test should still run even if the
                # host stream does not support reconfiguration.
                pass


def _preview_response(response: requests.Response, limit: int = 220) -> str:
    text = response.text.strip().encode("unicode_escape").decode("ascii")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _print_step(name: str, ok: bool, response: requests.Response | None = None, message: str | None = None) -> None:
    status_label = "PASS" if ok else "FAIL"
    print(f"{status_label} {name}")
    if response is not None:
        print(f"  status: {response.status_code}")
        print(f"  preview: {_preview_response(response)}")
    if message:
        print(f"  note: {message}")


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    return requests.request(method, url, timeout=30, **kwargs)


def _check_health(base_url: str) -> bool:
    url = f"{base_url}/health"
    try:
        response = _request("GET", url)
    except Exception as exc:
        _print_step("/health", False, message=str(exc))
        return False

    ok = False
    try:
        payload = response.json()
        ok = response.status_code == 200 and payload.get("status") == "ok"
    except Exception:
        ok = False

    _print_step("/health", ok, response)
    return ok


def _check_jobs_search(base_url: str, mode: str | None = None, query: str = "data scientist", limit: int = 5) -> bool:
    params = {"query": query, "limit": limit}
    if mode:
        params["mode"] = mode

    suffix = "semantic" if mode == "semantic" else "criteria"
    url = f"{base_url}/jobs/search"
    try:
        response = _request("GET", url, params=params)
    except Exception as exc:
        _print_step(f"/jobs/search ({suffix})", False, message=str(exc))
        return False

    ok = response.status_code == 200
    _print_step(f"/jobs/search ({suffix})", ok, response)
    return ok


def _check_resume_match(base_url: str) -> bool:
    url = f"{base_url}/resume/match"
    payload = {
        "user_id": "demo-smoke-user",
        "resume_text": "Python data scientist with machine learning, SQL, NLP, statistics, FastAPI, and data visualization experience.",
        "limit": 5,
    }
    try:
        response = _request("POST", url, json=payload)
    except Exception as exc:
        _print_step("/resume/match", False, message=str(exc))
        return False

    ok = response.status_code == 200
    _print_step("/resume/match", ok, response)
    return ok


def main() -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="Smoke test the local MVP API demo.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--skip-semantic", action="store_true")
    parser.add_argument("--skip-resume", action="store_true")
    args = parser.parse_args()

    overall_ok = True
    overall_ok &= _check_health(args.base_url)
    overall_ok &= _check_jobs_search(args.base_url, mode=None, query="data scientist", limit=5)

    if not args.skip_semantic:
        overall_ok &= _check_jobs_search(
            args.base_url,
            mode="semantic",
            query="python machine learning",
            limit=5,
        )

    if not args.skip_resume:
        overall_ok &= _check_resume_match(args.base_url)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
