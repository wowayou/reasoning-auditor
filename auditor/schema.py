"""Pydantic data contracts shared by the phase-zero modules."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects misspelled or unsupported fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClaimType(StrEnum):
    OBS = "OBS"
    ASSUMPTION = "ASSUMPTION"
    INFERENCE = "INFERENCE"
    PREDICTION = "PREDICTION"
    RECOMMENDATION = "RECOMMENDATION"


class EvidenceStatus(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"


class EdgeType(StrEnum):
    SUPPORTS = "SUPPORTS"


class Claim(StrictModel):
    id: str = Field(min_length=1)
    type: ClaimType
    content: str = Field(min_length=1)
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_CHECKED
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_with_verdict_requires_sources(self) -> Claim:
        if self.evidence_status in {
            EvidenceStatus.SUPPORTED,
            EvidenceStatus.CONTRADICTED,
        } and not self.sources:
            raise ValueError(
                "SUPPORTED and CONTRADICTED claims must include at least one source"
            )
        return self


class ClaimEdge(StrictModel):
    """A directed dependency: from_claim_id supports to_claim_id."""

    from_claim_id: str = Field(min_length=1)
    to_claim_id: str = Field(min_length=1)
    type: EdgeType = EdgeType.SUPPORTS


class ClaimGraph(StrictModel):
    original_text: str = Field(min_length=1)
    compressed_view: str = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    edges: list[ClaimEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> ClaimGraph:
        claim_ids = [claim.id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim ids must be unique")

        known_ids = set(claim_ids)
        adjacency: dict[str, list[str]] = {claim_id: [] for claim_id in claim_ids}
        seen_edges: set[tuple[str, str, EdgeType]] = set()

        for edge in self.edges:
            if edge.from_claim_id not in known_ids or edge.to_claim_id not in known_ids:
                raise ValueError("all edge endpoints must reference existing claims")
            if edge.from_claim_id == edge.to_claim_id:
                raise ValueError("self-referencing edges are not allowed")

            edge_key = (edge.from_claim_id, edge.to_claim_id, edge.type)
            if edge_key in seen_edges:
                raise ValueError("duplicate edges are not allowed")
            seen_edges.add(edge_key)
            adjacency[edge.from_claim_id].append(edge.to_claim_id)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(claim_id: str) -> None:
            if claim_id in visiting:
                raise ValueError("claim graph must be acyclic")
            if claim_id in visited:
                return
            visiting.add(claim_id)
            for child_id in adjacency[claim_id]:
                visit(child_id)
            visiting.remove(claim_id)
            visited.add(claim_id)

        for claim_id in claim_ids:
            visit(claim_id)
        return self


class ReasoningChain(StrictModel):
    claim_ids: list[str] = Field(min_length=1)


class LoadBearingAssumption(StrictModel):
    claim_id: str
    affected_conclusion_ids: list[str]
    reason: str


class WeakestLink(StrictModel):
    claim_id: str
    evidence_status: EvidenceStatus
    affected_conclusion_ids: list[str]
    reason: str


class GraphAnalysis(StrictModel):
    reasoning_chains: list[ReasoningChain] = Field(default_factory=list)
    load_bearing_assumptions: list[LoadBearingAssumption] = Field(
        default_factory=list
    )
    weakest_link: WeakestLink | None = None


class AlternativeExplanation(StrictModel):
    content: str = Field(min_length=1)
    exclusion_method: str = Field(min_length=1)
    required_data: list[str] = Field(min_length=1)
    cost: str = Field(min_length=1)


class CurrentJudgement(StrictModel):
    reasonable_insights: list[str] = Field(default_factory=list)
    unverified_extrapolations: list[str] = Field(default_factory=list)


class VerificationStep(StrictModel):
    experiment: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    duration: str = Field(min_length=1)


class RhetoricAssessment(StrictModel):
    flags: list[str] = Field(default_factory=list)
    risk: str = "NOT_CHECKED"


class AuditReport(StrictModel):
    graph: ClaimGraph
    analysis: GraphAnalysis
    rhetoric: RhetoricAssessment = Field(default_factory=RhetoricAssessment)
    alternatives: list[AlternativeExplanation] = Field(default_factory=list)
    judgement: CurrentJudgement = Field(default_factory=CurrentJudgement)
    verification_steps: list[VerificationStep] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
