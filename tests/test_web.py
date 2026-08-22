import json
import importlib
import time

import pytest
from fastapi import HTTPException

from auditor.web.app import AuditRequest, STATIC_DIR, create_app
from auditor.providers import DemoMockProvider


def route_endpoint(app, path: str):
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"route not found: {path}")


def test_web_static_assets_and_index_exist() -> None:
    app = create_app()
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert any(getattr(route, "path", None) == "/" for route in app.routes)
    assert "AI 观点审计器" in index
    assert 'aria-label="报告视图"' in index
    assert "配置 AI 模型" in index
    assert "后端代理" in index
    assert "常用供应商" in index
    assert "可分享报告" in index
    assert "机器可读数据" in index
    assert ".workspace" in css
    assert "height: calc(100vh - 68px)" in css
    assert "scrollbar-gutter: stable" in css
    assert ".alternative-help" in css
    assert "/api/audit" in js
    assert "renderJsonTree" in js
    assert "downloadArtifact" in js
    assert "失败时保留以便重试" in js
    assert "providerPresets" in js
    assert "/api/audit/jobs" in js
    assert "progress-steps" in index
    assert "审计提示" in js
    assert "一屏" not in index  # layout is expressed through CSS, not user-facing copy
    assert "它具体做什么？" in index
    assert "季节性、算法更新、网站改版" in index
    assert "关闭不影响声明图和承重假设分析" in index
    assert "provider-summary" in index
    assert "Mock 在本地运行，不发送 API Key" in js
    assert "先看最影响结论的一步" in js
    assert "优先验证这个声明" in js
    assert "transient_provider_config_allowed" in js
    assert "Key 只在本次请求的内存生命周期内使用" in index


def test_health_reports_provider_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    health = route_endpoint(create_app(), "/api/health")

    assert health() == {
        "status": "ok",
        "web_build": 10,
        "openai_configured": False,
        "openai_defaults": {"base_url_configured": False, "base_url": "", "model": ""},
        "transient_provider_config_allowed": True,
    }


def test_health_exposes_non_secret_provider_defaults(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "demo-model")
    health = route_endpoint(create_app(), "/api/health")

    assert health() == {
        "status": "ok",
        "web_build": 10,
        "openai_configured": True,
        "openai_defaults": {
            "base_url_configured": True,
            "base_url": "https://api.example.test/v1",
            "model": "demo-model",
        },
        "transient_provider_config_allowed": True,
    }


def test_audit_endpoint_returns_structured_markdown_and_json() -> None:
    audit = route_endpoint(create_app(), "/api/audit")

    payload = audit(
        AuditRequest(
            text="SEO 正在死亡，企业必须全面转向 ABM",
            provider="mock",
            include_alternatives=True,
        )
    )

    assert payload["report"]["rhetoric"]["risk"] == "HIGH"
    assert len(payload["report"]["graph"]["claims"]) == 5
    assert payload["markdown"].startswith("# AI观点审计报告")
    assert [stage["id"] for stage in payload["stages"]] == [
        "decompose", "analyze", "rhetoric", "alternatives", "verification", "report"
    ]
    assert all(stage["status"] == "completed" for stage in payload["stages"])
    assert payload["duration_ms"] >= 0
    assert json.loads(payload["json"])["graph"]["original_text"] == "SEO 正在死亡，企业必须全面转向 ABM"


def test_audit_endpoint_can_skip_alternatives() -> None:
    audit = route_endpoint(create_app(), "/api/audit")

    payload = audit(AuditRequest(text="观点", include_alternatives=False))

    assert payload["report"]["alternatives"] == []
    assert all(stage["id"] != "alternatives" for stage in payload["stages"])


def test_audit_job_endpoint_reports_completion() -> None:
    web_app = create_app()
    create_job = route_endpoint(web_app, "/api/audit/jobs")
    get_job = route_endpoint(web_app, "/api/audit/jobs/{job_id}")

    job = create_job(AuditRequest(text="观点", provider="mock"))
    assert job["job_id"]
    deadline = time.monotonic() + 2
    result = None
    while time.monotonic() < deadline:
        result = get_job(job["job_id"])
        if result["status"] == "completed":
            break
        time.sleep(0.01)

    assert result is not None
    assert result["status"] == "completed"
    assert result["result"]["report"]["graph"]["original_text"] == "观点"


def test_audit_request_rejects_empty_and_oversized_text() -> None:
    with pytest.raises(ValueError):
        AuditRequest(text="")
    with pytest.raises(ValueError):
        AuditRequest(text="x" * 100_001)
    with pytest.raises(ValueError):
        AuditRequest(text="观点", api_key="x" * 501)


def test_public_mode_rejects_transient_provider_configuration(monkeypatch) -> None:
    monkeypatch.setenv("AUDITOR_ALLOW_TRANSIENT_PROVIDER_CONFIG", "false")
    web_app = create_app()
    health = route_endpoint(web_app, "/api/health")
    audit = route_endpoint(web_app, "/api/audit")

    assert health()["transient_provider_config_allowed"] is False
    with pytest.raises(HTTPException, match="临时 Provider 配置已关闭"):
        audit(
            AuditRequest(
                text="观点",
                provider="openai-compatible",
                api_key="temporary-secret",
                base_url="https://example.test/v1",
                model="demo-model",
            )
        )


def test_audit_endpoint_reports_missing_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    audit = route_endpoint(create_app(), "/api/audit")

    with pytest.raises(Exception, match="OPENAI_API_KEY"):
        audit(AuditRequest(text="观点", provider="openai-compatible"))


def test_audit_endpoint_uses_transient_model_configuration(monkeypatch) -> None:
    web_app = importlib.import_module("auditor.web.app")
    captured: dict[str, object] = {}

    class CapturingProvider(DemoMockProvider):
        def __init__(self, **kwargs: object) -> None:
            super().__init__()
            captured.update(kwargs)

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(web_app, "OpenAICompatibleProvider", CapturingProvider)
    audit = route_endpoint(web_app.create_app(), "/api/audit")

    payload = audit(
        web_app.AuditRequest(
            text="观点",
            provider="openai-compatible",
            api_key="temporary-secret",
            base_url="https://example.test/v1",
            model="demo-model",
            timeout=12,
        )
    )

    assert payload["report"]["graph"]["original_text"] == "观点"
    assert "temporary-secret" not in json.dumps(payload, ensure_ascii=False)
    assert captured == {
        "api_key": "temporary-secret",
        "base_url": "https://example.test/v1",
        "model": "demo-model",
        "timeout": 12.0,
        "closed": True,
    }


def test_audit_request_hides_api_key_in_repr() -> None:
    request = AuditRequest(text="观点", api_key="temporary-secret")

    assert "temporary-secret" not in repr(request)
