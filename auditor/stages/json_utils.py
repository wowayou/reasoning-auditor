"""Small response normalizer for model JSON outputs."""

from __future__ import annotations

import json
from typing import Any


def parse_model_json(raw_response: str, expected: str) -> Any:
    """Parse raw JSON, accepting one complete Markdown code fence.

    Models often wrap otherwise valid JSON in `````json`` fences. We accept
    that exact wrapper but still reject prose before or after the payload.
    """

    if not isinstance(raw_response, str) or not raw_response.strip():
        raise ValueError("provider returned an empty response")

    candidate = raw_response.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) < 3:
            raise ValueError("provider response contains an empty code fence")
        language = lines[0][3:].strip().lower()
        if language not in {"", "json"}:
            raise ValueError("provider response uses an unsupported code fence")
        candidate = "\n".join(lines[1:-1]).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError("provider response is not valid JSON") from error

    if expected == "object" and not isinstance(payload, dict):
        raise ValueError("provider response must be a JSON object")
    if expected == "array" and not isinstance(payload, list):
        raise ValueError("provider response must be a JSON array")
    return payload
