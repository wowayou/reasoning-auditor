import json

from scripts.build_pages import build_site


def test_build_pages_creates_self_contained_static_demo(tmp_path) -> None:
    destination = build_site(tmp_path / "site")

    assert (destination / "index.html").exists()
    assert (destination / "static" / "app.js").exists()
    assert (destination / "static" / "style.css").exists()
    assert 'name="auditor-mode" content="static-mock"' in (
        destination / "index.html"
    ).read_text(encoding="utf-8")
    fixture = json.loads(
        (destination / "static" / "demo-report.json").read_text(encoding="utf-8")
    )
    assert fixture["mode"] == "static-mock"
    assert fixture["with_alternatives"]["report"]["graph"]["claims"]
    assert "api_key" not in json.dumps(fixture, ensure_ascii=False)
