from io import BytesIO, TextIOWrapper

from src.internhunter.common.logging import _ensure_utf8_text_stream


def test_ensure_utf8_text_stream_allows_unicode_output():
    raw_buffer = BytesIO()
    stream = TextIOWrapper(raw_buffer, encoding="cp1252", errors="strict")

    _ensure_utf8_text_stream(stream)

    stream.write("↓ Crawl4AI")
    stream.flush()

    assert raw_buffer.getvalue()
