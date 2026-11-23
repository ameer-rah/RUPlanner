import sys

import requests

from management import check_program_sources


def test_records_and_detects_source_changes(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / "sources.json"
    content = ["<p>Approved course</p><script>random()</script>"]

    def get(url, timeout):
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = content[0].encode()
        return response

    monkeypatch.setattr(check_program_sources, "SOURCES", {"example": "https://example.test"})
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(sys, "argv", ["check_program_sources", str(baseline), "--record"])
    assert check_program_sources.main() == 0

    monkeypatch.setattr(sys, "argv", ["check_program_sources", str(baseline)])
    content[0] = "<p>Approved   course</p><script>different()</script>"
    assert check_program_sources.main() == 0
    content[0] = "<p>New course</p>"
    assert check_program_sources.main() == 1
    assert "Review required: example" in capsys.readouterr().out


def test_source_failure_preserves_baseline(tmp_path, monkeypatch):
    baseline = tmp_path / "sources.json"
    baseline.write_text('{"example": "previous"}')

    def fail(url, timeout):
        raise requests.Timeout("upstream timeout")

    monkeypatch.setattr(requests, "get", fail)
    monkeypatch.setattr(sys, "argv", ["check_program_sources", str(baseline), "--record"])
    assert check_program_sources.main() == 2
    assert baseline.read_text() == '{"example": "previous"}'
