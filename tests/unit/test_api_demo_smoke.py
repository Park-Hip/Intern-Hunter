from src.scripts import api_demo_smoke


def test_configure_stdio_reconfigures_stdout_and_stderr(monkeypatch):
    calls = []

    class DummyStream:
        def __init__(self, name: str):
            self.name = name

        def reconfigure(self, **kwargs):
            calls.append((self.name, kwargs))

    monkeypatch.setattr(api_demo_smoke.sys, "stdout", DummyStream("stdout"))
    monkeypatch.setattr(api_demo_smoke.sys, "stderr", DummyStream("stderr"))

    api_demo_smoke._configure_stdio()

    assert calls == [
        ("stdout", {"encoding": "utf-8", "errors": "backslashreplace"}),
        ("stderr", {"encoding": "utf-8", "errors": "backslashreplace"}),
    ]


def test_preview_response_escapes_unicode():
    response = type("DummyResponse", (), {"text": "Tuyển dụng kỹ sư dữ liệu"})()

    preview = api_demo_smoke._preview_response(response, limit=220)

    assert "\\u" in preview
    assert "Tuyển" not in preview
