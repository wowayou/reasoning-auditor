import pytest
from pydantic import ValidationError

from auditor.schema import (
    Claim,
    ClaimEdge,
    ClaimGraph,
    ClaimType,
    EvidenceStatus,
)


def make_claim(claim_id: str, claim_type: ClaimType = ClaimType.OBS) -> Claim:
    return Claim(id=claim_id, type=claim_type, content=f"claim {claim_id}")


def test_claim_defaults_to_not_checked() -> None:
    claim = make_claim("c1")

    assert claim.evidence_status is EvidenceStatus.NOT_CHECKED
    assert claim.sources == []


@pytest.mark.parametrize(
    "status", [EvidenceStatus.SUPPORTED, EvidenceStatus.CONTRADICTED]
)
def test_evidence_verdict_requires_a_source(status: EvidenceStatus) -> None:
    with pytest.raises(ValidationError, match="must include at least one source"):
        Claim(id="c1", type=ClaimType.OBS, content="事实", evidence_status=status)


def test_graph_rejects_duplicate_claim_ids() -> None:
    with pytest.raises(ValidationError, match="claim ids must be unique"):
        ClaimGraph(
            original_text="原文",
            compressed_view="压缩观点",
            claims=[make_claim("c1"), make_claim("c1")],
        )


def test_graph_rejects_dangling_edge() -> None:
    with pytest.raises(ValidationError, match="edge endpoints"):
        ClaimGraph(
            original_text="原文",
            compressed_view="压缩观点",
            claims=[make_claim("c1")],
            edges=[ClaimEdge(from_claim_id="c1", to_claim_id="missing")],
        )


def test_graph_rejects_cycles() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        ClaimGraph(
            original_text="原文",
            compressed_view="压缩观点",
            claims=[make_claim("c1"), make_claim("c2")],
            edges=[
                ClaimEdge(from_claim_id="c1", to_claim_id="c2"),
                ClaimEdge(from_claim_id="c2", to_claim_id="c1"),
            ],
        )


def test_graph_accepts_a_valid_dag() -> None:
    graph = ClaimGraph(
        original_text="原文",
        compressed_view="压缩观点",
        claims=[make_claim("c1"), make_claim("c2", ClaimType.RECOMMENDATION)],
        edges=[ClaimEdge(from_claim_id="c1", to_claim_id="c2")],
    )

    assert graph.edges[0].from_claim_id == "c1"
