"""
Shared utility functions for the InternHunter project.

Single-source-of-truth for common operations used across layers.
"""


def normalize_url(url: str) -> str:
    """Canonical URL for dedup: strip query params, fragments, trailing slashes, and whitespace.

    Examples:
        >>> normalize_url("https://topcv.vn/job/123?ref=search#apply")
        'https://topcv.vn/job/123'
        >>> normalize_url("https://topcv.vn/job/123/")
        'https://topcv.vn/job/123'
    """
    if not url or not isinstance(url, str):
        return ""
    return url.split("?")[0].split("#")[0].strip().rstrip("/")
