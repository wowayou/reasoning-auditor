from auditor.graph.ops import GraphAnalyzer
from auditor.schema import Claim, ClaimEdge, ClaimGraph, ClaimType
from auditor.verification import VerificationPlanner


def test_planner_creates_bounded_steps_for_load_bearing_assumptions() -> None:
    graph = ClaimGraph(
        original_text="观点",
        compressed_view="压缩观点",
        claims=[
            Claim(id="obs", type=ClaimType.OBS, content="观察"),
            Claim(id="assumption", type=ClaimType.ASSUMPTION, content="假设"),
            Claim(id="recommendation", type=ClaimType.RECOMMENDATION, content="建议"),
        ],
        edges=[
            ClaimEdge(from_claim_id="obs", to_claim_id="assumption"),
            ClaimEdge(from_claim_id="assumption", to_claim_id="recommendation"),
        ],
    )
    analysis = GraphAnalyzer().analyze(graph)

    steps = VerificationPlanner().plan(graph, analysis)

    assert len(steps) == 1
    assert "假设" in steps[0].experiment
    assert steps[0].cost == "低到中"
    assert steps[0].duration == "1-2 周"


def test_planner_returns_no_step_for_an_unconnected_observation() -> None:
    graph = ClaimGraph(
        original_text="事实",
        compressed_view="事实",
        claims=[Claim(id="obs", type=ClaimType.OBS, content="事实")],
    )

    assert VerificationPlanner().plan(graph, GraphAnalyzer().analyze(graph)) == []
