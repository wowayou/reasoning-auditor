"""Find and validate alternative explanations through a Provider."""

from __future__ import annotations

from pydantic import ValidationError

from auditor.providers import Provider
from auditor.schema import AlternativeExplanation, ClaimGraph
from auditor.stages.json_utils import parse_model_json


class AlternativeError(ValueError):
    """Raised when a provider cannot produce valid alternatives."""


class AlternativeStage:
    """Request alternatives for a ClaimGraph without attempting evidence search."""

    prompt_prefix = (
        "针对下面的 ClaimGraph，列出可检验的普通替代解释。只返回 JSON 数组，"
        "每项必须包含 content、exclusion_method、required_data、cost；"
        "required_data 必须是字符串数组，即使只有一项也必须使用数组；"
        "示例：[{\"content\":\"季节性\",\"exclusion_method\":\"同比比较\","
        "\"required_data\":[\"至少12个月历史数据\"],\"cost\":\"低\"}]。"
        "如果没有合格解释，返回空数组。\n\nClaimGraph："
    )

    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.discarded_count = 0
        self.warning: str | None = None

    def run(self, graph: ClaimGraph) -> list[AlternativeExplanation]:
        prompt = f"{self.prompt_prefix}{graph.model_dump_json()}"
        raw_response = self.provider.complete(prompt)
        try:
            payload = parse_model_json(raw_response, "array")
        except ValueError:
            try:
                payload = parse_model_json(raw_response, "object")
            except ValueError:
                self.warning = "替代解释响应不是可解析的 JSON 数组，已跳过替代解释。"
                return []

        if isinstance(payload, dict):
            for key in ("alternatives", "items", "data", "results"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
            else:
                self.warning = "替代解释响应缺少数组字段，已跳过替代解释。"
                return []
        alternatives: list[AlternativeExplanation] = []
        self.discarded_count = 0
        self.warning = None
        for item in payload:
            if not isinstance(item, dict):
                self.discarded_count += 1
                continue
            normalized = dict(item)
            aliases = {
                "explanation": "content",
                "how_to_rule_out": "exclusion_method",
                "data_needed": "required_data",
            }
            for alias, canonical in aliases.items():
                if canonical not in normalized and alias in normalized:
                    normalized[canonical] = normalized[alias]
                normalized.pop(alias, None)
            required_data = normalized.get("required_data")
            if isinstance(required_data, str) and required_data.strip():
                normalized["required_data"] = [
                    part.strip()
                    for part in required_data.replace("\n", ",").split(",")
                    if part.strip()
                ]
            try:
                alternatives.append(AlternativeExplanation.model_validate(normalized))
            except ValidationError:
                # PRD: alternatives without exclusion method, data, or cost
                # are discarded instead of failing the whole audit.
                self.discarded_count += 1
                continue
        if self.discarded_count:
            self.warning = f"已丢弃 {self.discarded_count} 条不完整的替代解释。"
        return alternatives
