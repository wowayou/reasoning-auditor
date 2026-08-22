"""Provider interfaces for deterministic phase-one orchestration."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
import re
from typing import Protocol
from urllib.parse import urlparse

import httpx


class Provider(Protocol):
    def complete(self, prompt: str) -> str:
        """Return a completion for a prompt."""


class ProviderError(RuntimeError):
    """A safe, user-facing error from a model provider."""


class MockProvider:
    """A deterministic provider for local development and tests.

    If a response mapping is supplied, an exact prompt match wins; otherwise
    ``default_response`` is returned. Prompts are recorded in call order.
    """

    def __init__(
        self,
        responses: Mapping[str, str] | None = None,
        default_response: str = "MOCK_RESPONSE",
    ) -> None:
        self._responses = dict(responses or {})
        self.default_response = default_response
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        self.calls.append(prompt)
        return self._responses.get(prompt, self.default_response)


class OpenAICompatibleProvider:
    """Synchronous OpenAI-compatible Chat Completions provider.

    The API key is read from ``OPENAI_API_KEY`` by default and is never
    included in exception messages. ``base_url`` can point to any service that
    implements ``POST /chat/completions``.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key or not resolved_key.strip():
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.api_key = resolved_key
        self.base_url = self._validate_base_url(
            base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        )
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        if not self.model.strip():
            raise ValueError("model must be a non-empty string")
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        candidate = base_url.strip().rstrip("/")
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("base_url must be an http(s) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url cannot contain credentials, query, or fragment")
        loopback_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme == "http" and parsed.hostname not in loopback_hosts:
            raise ValueError("plain HTTP base_url is only allowed for localhost")
        return candidate

    def complete(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise ProviderError("provider request timed out") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = self._safe_error_detail(error.response, self.api_key)
            message = {
                400: "请求被供应商拒绝。请检查模型名称、请求格式或 Base URL。",
                401: "供应商拒绝了 API Key（HTTP 401）。请确认 Key 属于当前供应商，且没有过期。",
                403: "供应商拒绝了访问（HTTP 403）。请检查账号权限、模型权限或区域限制。",
                404: "供应商找不到接口或模型（HTTP 404）。请确认 Base URL 是 API 根地址，模型名称可用。",
                408: "供应商请求超时（HTTP 408）。请稍后重试或增加 Timeout。",
                429: "供应商限流（HTTP 429）。请稍后重试或检查配额。",
            }.get(status, f"供应商返回 HTTP {status}。")
            if detail:
                message = f"{message} 供应商信息：{detail}"
            raise ProviderError(message) from error
        except httpx.HTTPError as error:
            raise ProviderError("provider request failed") from error
        except ValueError as error:
            raise ProviderError("provider returned invalid JSON") from error

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError("provider response is missing choices[0].message.content") from error
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            content = "".join(parts)
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("provider returned empty content")
        return content

    @staticmethod
    def _safe_error_detail(response: httpx.Response, api_key: str) -> str:
        """Extract a short provider message without exposing credentials."""
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error", payload)
                if isinstance(error, dict):
                    detail = str(error.get("message") or error.get("detail") or "")
                elif isinstance(error, str):
                    detail = error
        except ValueError:
            detail = response.text
        detail = re.sub(r"(?i)(bearer|api[-_ ]?key)\s+[^\s,;]+", r"\1 [redacted]", detail)
        detail = detail.replace(api_key, "[redacted]").strip()
        return detail[:240]

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenAICompatibleProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class DemoMockProvider:
    """A deterministic end-to-end provider used by the acceptance CLI.

    It emits a small, structurally valid graph and one ordinary alternative
    explanation. It is deliberately a demo fixture, not a truth engine.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        self.calls.append(prompt)
        if "针对下面的 ClaimGraph" in prompt:
            return json.dumps(
                [
                    {
                        "content": "季节性波动",
                        "exclusion_method": "比较去年同期与当前周期的同类指标",
                        "required_data": ["历史周期数据"],
                        "cost": "低",
                    }
                ],
                ensure_ascii=False,
            )

        viewpoint = prompt.rsplit("观点：", 1)[-1].strip()
        if "SEO" in viewpoint and "ABM" in viewpoint:
            return json.dumps(
                {
                    "compressed_view": "部分 B2B 搜索流量变化被外推为 SEO 重要性下降，并据此建议增加 ABM 投入。",
                    "claims": [
                        {
                            "id": "c1",
                            "type": "OBS",
                            "content": "部分 B2B 网站自然流量下降。",
                        },
                        {
                            "id": "c2",
                            "type": "ASSUMPTION",
                            "content": "流量下降主要由 AI 搜索导致。",
                        },
                        {
                            "id": "c3",
                            "type": "ASSUMPTION",
                            "content": "ABM 可以有效替代 SEO。",
                        },
                        {
                            "id": "c4",
                            "type": "PREDICTION",
                            "content": "SEO 重要性将持续下降。",
                        },
                        {
                            "id": "c5",
                            "type": "RECOMMENDATION",
                            "content": "企业增加 ABM 投入。",
                        },
                    ],
                    "edges": [
                        {"from_claim_id": "c1", "to_claim_id": "c2"},
                        {"from_claim_id": "c2", "to_claim_id": "c3"},
                        {"from_claim_id": "c3", "to_claim_id": "c4"},
                        {"from_claim_id": "c4", "to_claim_id": "c5"},
                    ],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "compressed_view": viewpoint,
                "claims": [
                    {
                        "id": "c1",
                        "type": "OBS",
                        "content": "输入观点包含一个需要拆解的判断。",
                    },
                    {
                        "id": "c2",
                        "type": "ASSUMPTION",
                        "content": "该判断中的因果关系与适用范围成立。",
                    },
                    {
                        "id": "c3",
                        "type": "RECOMMENDATION",
                        "content": "在采取大规模行动前先进行小规模验证。",
                    },
                ],
                "edges": [
                    {"from_claim_id": "c1", "to_claim_id": "c2"},
                    {"from_claim_id": "c2", "to_claim_id": "c3"},
                ],
            },
            ensure_ascii=False,
        )
