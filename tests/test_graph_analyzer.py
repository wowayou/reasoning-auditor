from auditor.graph.ops import GraphAnalyzer
from auditor.schema import (
    Claim,
    ClaimEdge,
    ClaimGraph,
    ClaimType,
    EvidenceStatus,
)


def claim(
    claim_id: str,
    claim_type: ClaimType,
    status: EvidenceStatus = EvidenceStatus.NOT_CHECKED,
    sources: list[str] | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        type=claim_type,
        content=f"content {claim_id}",
        evidence_status=status,
        sources=sources or [],
    )


def test_analyzer_extracts_all_root_to_terminal_chains() -> None:
    graph = ClaimGraph(
        original_text="观点",
        compressed_view="压缩观点",
        claims=[
            claim("obs", ClaimType.OBS),
            claim("assumption", ClaimType.ASSUMPTION),
            claim("prediction", ClaimType.PREDICTION),
            claim("recommendation", ClaimType.RECOMMENDATION),
        ],
        edges=[
            ClaimEdge(from_claim_id="obs", to_claim_id="assumption"),
            ClaimEdge(from_claim_id="assumption", to_claim_id="prediction"),
            ClaimEdge(from_claim_id="assumption", to_claim_id="recommendation"),
        ],
    )

    analysis = GraphAnalyzer().analyze(graph)

    assert [chain.claim_ids for chain in analysis.reasoning_chains] == [
        ["obs", "assumption", "prediction"],
        ["obs", "assumption", "recommendation"],
    ]


def test_analyzer_ranks_assumption_by_number_of_affected_conclusions() -> None:
    graph = ClaimGraph(
        original_text="观点",
        compressed_view="压缩观点",
        claims=[
            claim("a1", ClaimType.ASSUMPTION),
            claim("a2", ClaimType.ASSUMPTION),
            claim("p1", ClaimType.PREDICTION),
            claim("r1", ClaimType.RECOMMENDATION),
        ],
        edges=[
            ClaimEdge(from_claim_id="a1", to_claim_id="p1"),
            ClaimEdge(from_claim_id="a1", to_claim_id="r1"),
            ClaimEdge(from_claim_id="a2", to_claim_id="r1"),
        ],
    )

    analysis = GraphAnalyzer().analyze(graph)

    assert [item.claim_id for item in analysis.load_bearing_assumptions] == [
        "a1",
        "a2",
    ]
    assert analysis.load_bearing_assumptions[0].affected_conclusion_ids == [
        "p1",
        "r1",
    ]


def test_contradicted_dependency_is_the_weakest_link() -> None:
    graph = ClaimGraph(
        original_text="观点",
        compressed_view="压缩观点",
        claims=[
            claim(
                "obs",
                ClaimType.OBS,
                EvidenceStatus.SUPPORTED,
                ["https://example.com/source"],
            ),
            claim(
                "assumption",
                ClaimType.ASSUMPTION,
                EvidenceStatus.CONTRADICTED,
                ["https://example.com/counter-evidence"],
            ),
            claim("recommendation", ClaimType.RECOMMENDATION),
        ],
        edges=[
            ClaimEdge(from_claim_id="obs", to_claim_id="assumption"),
            ClaimEdge(from_claim_id="assumption", to_claim_id="recommendation"),
        ],
    )

    weakest = GraphAnalyzer().analyze(graph).weakest_link

    assert weakest is not None
    assert weakest.claim_id == "assumption"
    assert weakest.evidence_status is EvidenceStatus.CONTRADICTED
    assert weakest.affected_conclusion_ids == ["recommendation"]


def test_standalone_observation_has_no_weakest_conclusion_link() -> None:
    graph = ClaimGraph(
        original_text="事实陈述",
        compressed_view="事实陈述",
        claims=[claim("obs", ClaimType.OBS)],
    )

    analysis = GraphAnalyzer().analyze(graph)

    assert analysis.reasoning_chains[0].claim_ids == ["obs"]
    assert analysis.load_bearing_assumptions == []
    assert analysis.weakest_link is None
