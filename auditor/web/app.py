"""FastAPI application and HTTP contract for the browser UI."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from threading import Lock
from uuid import uuid4
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr

from auditor.pipeline import AuditPipeline
from auditor.providers import DemoMockProvider, OpenAICompatibleProvider, ProviderError
from auditor.render import JSONReportRenderer, MarkdownReportRenderer


STATIC_DIR = Path(__file__).parent / "static"
WEB_BUILD = 10


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AuditRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    provider: Literal["mock", "openai-compatible"] = "mock"
    include_alternatives: bool = True
    api_key: SecretStr | None = Field(default=None, max_length=500, repr=False)
    base_url: str | None = Field(default=None, max_length=2_000)
    model: str | None = Field(default=None, max_length=200)
    timeout: float = Field(default=60.0, gt=0, le=300)


def create_app() -> FastAPI:
    app = FastAPI(title="AI Reasoning Auditor", version="0.1.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    jobs: dict[str, dict[str, object]] = {}
    jobs_lock = Lock()
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audit-job")
    allow_transient_provider_config = _env_flag(
        "AUDITOR_ALLOW_TRANSIENT_PROVIDER_CONFIG", True
    )

    stage_labels = {
        "decompose": "拆解声明",
        "analyze": "分析推理链",
        "rhetoric": "扫描修辞风险",
        "alternatives": "寻找替代解释",
        "verification": "规划验证步骤",
        "report": "生成审计报告",
    }

    def validate_provider_configuration(request: AuditRequest) -> None:
        if request.provider == "openai-compatible" and not allow_transient_provider_config:
            if request.api_key or request.base_url or request.model:
                raise ValueError(
                    "临时 Provider 配置已关闭；请使用 Mock，或在服务端设置 OPENAI_API_KEY、"
                    "OPENAI_BASE_URL 和 OPENAI_MODEL"
                )

    def execute_audit(
        request: AuditRequest,
        on_stage_update=None,
    ) -> dict[str, object]:
        request_started = perf_counter()
        stages: list[dict[str, object]] = []
        stage_started: float | None = None

        def on_stage(name: str) -> None:
            nonlocal stage_started
            now = perf_counter()
            if stages and stage_started is not None:
                stages[-1].update(
                    status="completed",
                    duration_ms=round((now - stage_started) * 1000),
                )
            stages.append(
                {"id": name, "label": stage_labels[name], "status": "running"}
            )
            stage_started = now
            if on_stage_update is not None:
                on_stage_update(stages)

        validate_provider_configuration(request)

        provider = (
            DemoMockProvider()
            if request.provider == "mock"
            else OpenAICompatibleProvider(
                api_key=request.api_key.get_secret_value() if request.api_key else None,
                base_url=request.base_url,
                model=request.model,
                timeout=request.timeout,
            )
        )
        try:
            report = AuditPipeline(provider).run(
                request.text,
                include_alternatives=request.include_alternatives,
                on_stage=on_stage,
            )
            if stages and stage_started is not None:
                stages[-1].update(
                    status="completed",
                    duration_ms=round((perf_counter() - stage_started) * 1000),
                )
            result = {
                "report": report.model_dump(mode="json"),
                "markdown": MarkdownReportRenderer().render(report),
                "json": JSONReportRenderer().render(report),
                "stages": stages,
                "duration_ms": round((perf_counter() - request_started) * 1000),
            }
            if on_stage_update is not None:
                on_stage_update(stages)
            return result
        finally:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "web_build": WEB_BUILD,
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "openai_defaults": {
                "base_url_configured": bool(os.getenv("OPENAI_BASE_URL")),
                "base_url": os.getenv("OPENAI_BASE_URL", ""),
                "model": os.getenv("OPENAI_MODEL", ""),
            },
            "transient_provider_config_allowed": allow_transient_provider_config,
        }

    @app.post("/api/audit")
    def audit(request: AuditRequest) -> dict[str, object]:
        try:
            return execute_audit(request)
        except (ValueError, ProviderError) as error:
            status_code = 502 if isinstance(error, ProviderError) else 422
            raise HTTPException(status_code=status_code, detail=str(error)) from error

    def run_job(job_id: str, request: AuditRequest) -> None:
        def update(stages: list[dict[str, object]]) -> None:
            with jobs_lock:
                job = jobs.get(job_id)
                if job is not None:
                    job["status"] = "running"
                    job["stages"] = [dict(stage) for stage in stages]
                    job["current_stage"] = stages[-1]["id"] if stages else None
                    job["elapsed_ms"] = round(
                        (perf_counter() - float(job["started_at"])) * 1000
                    )

        try:
            result = execute_audit(request, update)
        except (ValueError, ProviderError) as error:
            with jobs_lock:
                job = jobs[job_id]
                job.update(
                    status="failed",
                    error=str(error),
                    elapsed_ms=round(
                        (perf_counter() - float(job["started_at"])) * 1000
                    ),
                )
        except Exception:
            with jobs_lock:
                job = jobs[job_id]
                job.update(
                    status="failed",
                    error="审计服务发生未预期错误，请查看服务端日志。",
                    elapsed_ms=round(
                        (perf_counter() - float(job["started_at"])) * 1000
                    ),
                )
        else:
            with jobs_lock:
                job = jobs[job_id]
                job.update(
                    status="completed",
                    current_stage=None,
                    stages=result["stages"],
                    elapsed_ms=result["duration_ms"],
                    result=result,
                )

    @app.post("/api/audit/jobs", status_code=202)
    def create_audit_job(request: AuditRequest) -> dict[str, str]:
        try:
            validate_provider_configuration(request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        job_id = uuid4().hex
        with jobs_lock:
            if len(jobs) >= 100:
                finished = [
                    key
                    for key, value in jobs.items()
                    if value["status"] in {"completed", "failed"}
                ]
                for key in finished[: max(1, len(jobs) - 99)]:
                    jobs.pop(key, None)
            jobs[job_id] = {
                "status": "queued",
                "current_stage": None,
                "stages": [],
                "elapsed_ms": 0,
                "started_at": perf_counter(),
            }
        executor.submit(run_job, job_id, request)
        return {"job_id": job_id}

    @app.get("/api/audit/jobs/{job_id}")
    def get_audit_job(job_id: str) -> dict[str, object]:
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="audit job not found")
            response = {key: value for key, value in job.items() if key != "started_at"}
            if job["status"] in {"queued", "running"}:
                response["elapsed_ms"] = round(
                    (perf_counter() - float(job["started_at"])) * 1000
                )
            return response

    return app


app = create_app()
