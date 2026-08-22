"""Build the GitHub Pages static Mock demo."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from auditor.pipeline import AuditPipeline
from auditor.providers import DemoMockProvider
from auditor.render import JSONReportRenderer, MarkdownReportRenderer


ROOT = Path(__file__).resolve().parents[1]
STATIC_SOURCE = ROOT / "auditor" / "web" / "static"


def _run_demo(include_alternatives: bool) -> dict[str, object]:
    report = AuditPipeline(DemoMockProvider()).run(
        "SEO 正在死亡，企业应该转向 ABM。",
        include_alternatives=include_alternatives,
    )
    return {
        "report": report.model_dump(mode="json"),
        "markdown": MarkdownReportRenderer().render(report),
        "json": JSONReportRenderer().render(report),
        "stages": [
            {"id": stage, "label": stage, "status": "completed"}
            for stage in ("decompose", "analyze", "rhetoric", "alternatives", "verification", "report")
            if include_alternatives or stage != "alternatives"
        ],
        "duration_ms": 0,
    }


def build_site(destination: Path) -> Path:
    """Copy the static UI and generate deterministic, local-only demo data."""
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "static").mkdir(parents=True)
    index = (STATIC_SOURCE / "index.html").read_text(encoding="utf-8")
    index = index.replace(
        '<meta name="description" content="AI 观点审计器">',
        '<meta name="description" content="AI 观点审计器">\n'
        '    <meta name="auditor-mode" content="static-mock">',
    )
    (destination / "index.html").write_text(index, encoding="utf-8")
    shutil.copy2(STATIC_SOURCE / "style.css", destination / "static" / "style.css")
    shutil.copy2(STATIC_SOURCE / "app.js", destination / "static" / "app.js")
    demo = {
        "mode": "static-mock",
        "notice": "GitHub Pages 静态演示只运行本地 Mock，不连接任何模型供应商。",
        "with_alternatives": _run_demo(True),
        "without_alternatives": _run_demo(False),
    }
    (destination / "static" / "demo-report.json").write_text(
        json.dumps(demo, ensure_ascii=False), encoding="utf-8"
    )
    # Prevent Jekyll from treating underscore-prefixed future assets specially.
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    return destination


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    print(build_site(target))
