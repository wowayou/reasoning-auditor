import json

import pytest

from auditor.providers import MockProvider
from auditor.schema import AlternativeExplanation, Claim, ClaimEdge, ClaimGraph, ClaimType
from auditor.stages.alternatives import AlternativeError, AlternativeStage
from auditor.stages.decompose import DecomposeError, DecomposeStage


def decomposition_payload() -> dict[str, object]:
    return {
        "compressed_view": "流量下降被外推为 SEO 失效。",
        "claims": [
            {"id": "obs", "type": "OBS", "content": "部分流量下降。"},
            {
                "id": "assumption",
                "type": "ASSUMPTION",
                "content": "下降主要由 AI 搜索导致。",
            },
            {
                "id": "recommendation",
                "type": "RECOMMENDATION",
                "content": "增加 ABM 投入。",
            },
        ],
        "edges": [
            {"from_claim_id": "obs", "to_claim_id": "assumption"},
            {"from_claim_id": "assumption", "to_claim_id": "recommendation"},
        ],
    }


def make_graph() -> ClaimGraph:
    return ClaimGraph(
        original_text="网站流量下降，所以要增加 ABM。",
        compressed_view="流量下降被外推为转向 ABM 的理由。",
        claims=[
            Claim(id="obs", type=ClaimType.OBS, content="流量下降。"),
            Claim(id="recommendation", type=ClaimType.RECOMMENDATION, content="增加 ABM。"),
        ],
        edges=[ClaimEdge(from_claim_id="obs", to_claim_id="recommendation")],
    )


def test_decompose_stage_builds_claim_graph_and_owns_original_text() -> None:
    provider = MockProvider(default_response=json.dumps(decomposition_payload()))

    graph = DecomposeStage(provider).run("SEO 正在死亡，企业应该转向 ABM。")

    assert graph.original_text == "SEO 正在死亡，企业应该转向 ABM。"
    assert graph.compressed_view == "流量下降被外推为 SEO 失效。"
    assert [claim.id for claim in graph.claims] == ["obs", "assumption", "recommendation"]
    assert len(provider.calls) == 1
    assert "只返回 JSON" in provider.calls[0]


def test_decompose_stage_accepts_a_complete_json_code_fence() -> None:
    provider = MockProvider(
        default_response=f"```json\n{json.dumps(decomposition_payload())}\n```"
    )

    graph = DecomposeStage(provider).run("观点")

    assert len(graph.claims) == 3


def test_decompose_stage_accepts_one_json_fence_with_short_preamble() -> None:
    provider = MockProvider(
        default_response=f"结果如下：\n```json\n{json.dumps(decomposition_payload())}\n```"
    )

    graph = DecomposeStage(provider).run("观点")

    assert len(graph.claims) == 3


def test_decompose_stage_normalizes_statement_source_target_aliases() -> None:
    payload = {
        "compressed_view": "SEO 被外推为失效，因此建议转向 ABM。",
        "claims": [
            {"id": "c1", "type": "OBS", "statement": "自然流量下降。"},
            {"id": "c2", "type": "RECOMMENDATION", "statement": "增加 ABM 投入。"},
        ],
        "edges": [{"source": "c1", "target": "c2", "relation": "支持"}],
    }
    graph = DecomposeStage(MockProvider(default_response=json.dumps(payload))).run("观点")

    assert [claim.content for claim in graph.claims] == ["自然流量下降。", "增加 ABM 投入。"]
    assert graph.edges[0].from_claim_id == "c1"
    assert graph.edges[0].to_claim_id == "c2"


def test_decompose_stage_repairs_one_invalid_provider_response() -> None:
    valid = json.dumps(decomposition_payload())

    class SequenceProvider:
        def __init__(self) -> None:
            self.responses = ["not json", valid]
            self.calls: list[str] = []

        def complete(self, prompt: str) -> str:
            self.calls.append(prompt)
            return self.responses.pop(0)

    provider = SequenceProvider()
    graph = DecomposeStage(provider).run("观点")

    assert len(graph.claims) == 3
    assert len(provider.calls) == 2
    assert "修复下面的 ClaimGraph JSON" in provider.calls[1]


def test_decompose_stage_stops_after_one_repair_attempt() -> None:
    provider = MockProvider(default_response="not json")

    with pytest.raises(DecomposeError, match="one automatic repair"):
        DecomposeStage(provider).run("观点")

    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    "response, error_message",
    [
        ("", "empty response"),
        ("not json", "not valid JSON"),
        ("[]", "JSON object"),
        (json.dumps({"compressed_view": "x", "claims": []}), "validation"),
    ],
)
def test_decompose_stage_rejects_invalid_provider_output(
    response: str, error_message: str
) -> None:
    provider = MockProvider(default_response=response)

    with pytest.raises(DecomposeError, match=error_message):
        DecomposeStage(provider).run("观点")


def test_decompose_stage_rejects_empty_input_without_calling_provider() -> None:
    provider = MockProvider()

    with pytest.raises(ValueError, match="non-empty"):
        DecomposeStage(provider).run("  ")
    assert provider.calls == []


def test_alternative_stage_returns_valid_alternatives() -> None:
    alternatives = [
        {
            "content": "算法更新",
            "exclusion_method": "对比更新时间前后的排名",
            "required_data": ["GSC 数据"],
            "cost": "低",
        }
    ]
    provider = MockProvider(default_response=json.dumps(alternatives))

    result = AlternativeStage(provider).run(make_graph())

    assert result == [AlternativeExplanation.model_validate(alternatives[0])]
    assert "ClaimGraph" in provider.calls[0]


def test_alternative_stage_normalizes_string_required_data() -> None:
    response = json.dumps(
        [
            {
                "content": "季节性",
                "exclusion_method": "同比比较",
                "required_data": "至少 12 个月历史数据",
                "cost": "低",
            }
        ]
    )

    result = AlternativeStage(MockProvider(default_response=response)).run(make_graph())

    assert result[0].required_data == ["至少 12 个月历史数据"]


def test_alternative_stage_discards_incomplete_items_without_failing_report() -> None:
    response = json.dumps(
        [
            {
                "content": "缺少成本",
                "exclusion_method": "检查数据",
                "required_data": ["数据"],
            },
            {
                "explanation": "竞争变化",
                "how_to_rule_out": "对比竞争对手份额",
                "data_needed": "市场份额数据",
                "cost": "中",
            },
        ]
    )

    result = AlternativeStage(MockProvider(default_response=response)).run(make_graph())

    assert len(result) == 1
    assert result[0].content == "竞争变化"
    assert result[0].required_data == ["市场份额数据"]


def test_alternative_stage_degrades_on_empty_provider_output() -> None:
    stage = AlternativeStage(MockProvider(default_response=""))

    assert stage.run(make_graph()) == []
    assert stage.warning == "替代解释响应不是可解析的 JSON 数组，已跳过替代解释。"


def test_alternative_stage_allows_no_qualified_explanations() -> None:
    result = AlternativeStage(MockProvider(default_response="[]")).run(make_graph())

    assert result == []


def test_alternative_stage_accepts_wrapped_items_and_malformed_response_degrades() -> None:
    wrapped = json.dumps(
        {
            "alternatives": [
                {
                    "content": "算法更新",
                    "exclusion_method": "对比更新时间",
                    "required_data": "排名数据, 流量数据",
                    "cost": "低",
                }
            ]
        }
    )
    stage = AlternativeStage(MockProvider(default_response=wrapped))
    result = stage.run(make_graph())
    assert result[0].required_data == ["排名数据", "流量数据"]

    malformed = AlternativeStage(MockProvider(default_response="not json"))
    assert malformed.run(make_graph()) == []
    assert malformed.warning is not None


def test_alternative_stage_accepts_a_complete_json_code_fence() -> None:
    response = json.dumps(
        [
            {
                "content": "季节性",
                "exclusion_method": "同比比较",
                "required_data": ["历史数据"],
                "cost": "低",
            }
        ]
    )

    result = AlternativeStage(MockProvider(default_response=f"```json\n{response}\n```" )).run(
        make_graph()
    )

    assert result[0].content == "季节性"
