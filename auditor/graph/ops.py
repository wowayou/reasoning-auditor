"""Deterministic structural analysis for ClaimGraph instances."""

from __future__ import annotations

from collections.abc import Iterable

from auditor.schema import (
    Claim,
    ClaimGraph,
    ClaimType,
    EvidenceStatus,
    GraphAnalysis,
    LoadBearingAssumption,
    ReasoningChain,
    WeakestLink,
)


CONCLUSION_TYPES = {
    ClaimType.INFERENCE,
    ClaimType.PREDICTION,
    ClaimType.RECOMMENDATION,
}

# Lower means structurally weaker. These are categories, not confidence scores.
EVIDENCE_WEAKNESS_ORDER = {
    EvidenceStatus.CONTRADICTED: 0,
    EvidenceStatus.UNVERIFIED: 1,
    EvidenceStatus.NOT_CHECKED: 2,
    EvidenceStatus.SUPPORTED: 3,
}

TYPE_RISK_ORDER = {
    ClaimType.ASSUMPTION: 0,
    ClaimType.INFERENCE: 1,
    ClaimType.PREDICTION: 2,
    ClaimType.OBS: 3,
    ClaimType.RECOMMENDATION: 4,
}


class GraphAnalyzer:
    """Find reasoning chains, load-bearing assumptions, and the weakest link."""

    def analyze(self, graph: ClaimGraph) -> GraphAnalysis:
        claims_by_id = {claim.id: claim for claim in graph.claims}
        claim_order = {claim.id: index for index, claim in enumerate(graph.claims)}
        outgoing = {claim.id: [] for claim in graph.claims}
        incoming = {claim.id: [] for claim in graph.claims}

        for edge in graph.edges:
            outgoing[edge.from_claim_id].append(edge.to_claim_id)
            incoming[edge.to_claim_id].append(edge.from_claim_id)

        terminal_ids = [claim.id for claim in graph.claims if not outgoing[claim.id]]
        conclusion_ids = [
            claim_id
            for claim_id in terminal_ids
            if claims_by_id[claim_id].type in CONCLUSION_TYPES
        ]

        chains = self._find_chains(graph, incoming, outgoing, terminal_ids)
        affected_by_claim = {
            claim.id: self._reachable_conclusions(
                claim.id, outgoing, conclusion_ids, claim_order
            )
            for claim in graph.claims
        }

        assumptions = [
            LoadBearingAssumption(
                claim_id=claim.id,
                affected_conclusion_ids=affected_by_claim[claim.id],
                reason=self._assumption_reason(affected_by_claim[claim.id]),
            )
            for claim in graph.claims
            if claim.type is ClaimType.ASSUMPTION and affected_by_claim[claim.id]
        ]
        assumptions.sort(
            key=lambda item: (
                -len(item.affected_conclusion_ids),
                claim_order[item.claim_id],
            )
        )

        weakest_link = self._find_weakest_link(
            graph.claims,
            affected_by_claim,
            conclusion_ids,
            incoming,
            claim_order,
        )

        return GraphAnalysis(
            reasoning_chains=chains,
            load_bearing_assumptions=assumptions,
            weakest_link=weakest_link,
        )

    def _find_chains(
        self,
        graph: ClaimGraph,
        incoming: dict[str, list[str]],
        outgoing: dict[str, list[str]],
        terminal_ids: list[str],
    ) -> list[ReasoningChain]:
        roots = [claim.id for claim in graph.claims if not incoming[claim.id]]
        terminal_set = set(terminal_ids)
        chains: list[ReasoningChain] = []

        def walk(claim_id: str, path: list[str]) -> None:
            next_path = [*path, claim_id]
            if claim_id in terminal_set:
                chains.append(ReasoningChain(claim_ids=next_path))
                return
            for child_id in outgoing[claim_id]:
                walk(child_id, next_path)

        for root_id in roots:
            walk(root_id, [])
        return chains

    def _reachable_conclusions(
        self,
        start_id: str,
        outgoing: dict[str, list[str]],
        conclusion_ids: list[str],
        claim_order: dict[str, int],
    ) -> list[str]:
        conclusions = set(conclusion_ids)
        reached: set[str] = set()
        pending = list(outgoing[start_id])

        while pending:
            claim_id = pending.pop()
            if claim_id in reached:
                continue
            reached.add(claim_id)
            pending.extend(outgoing[claim_id])

        return sorted(reached & conclusions, key=claim_order.__getitem__)

    def _find_weakest_link(
        self,
        claims: Iterable[Claim],
        affected_by_claim: dict[str, list[str]],
        conclusion_ids: list[str],
        incoming: dict[str, list[str]],
        claim_order: dict[str, int],
    ) -> WeakestLink | None:
        claim_list = list(claims)
        dependency_candidates = [
            claim for claim in claim_list if affected_by_claim[claim.id]
        ]

        # A standalone conclusion has no dependency. It is still auditable by its
        # own evidence state, so use it only when no upstream candidate exists.
        if not dependency_candidates:
            dependency_candidates = [
                claim
                for claim in claim_list
                if claim.id in conclusion_ids and not incoming[claim.id]
            ]
        if not dependency_candidates:
            return None

        weakest = min(
            dependency_candidates,
            key=lambda claim: (
                EVIDENCE_WEAKNESS_ORDER[claim.evidence_status],
                TYPE_RISK_ORDER[claim.type],
                -len(affected_by_claim[claim.id]),
                claim_order[claim.id],
            ),
        )
        affected = affected_by_claim[weakest.id]
        if not affected and weakest.id in conclusion_ids:
            affected = [weakest.id]

        return WeakestLink(
            claim_id=weakest.id,
            evidence_status=weakest.evidence_status,
            affected_conclusion_ids=affected,
            reason=self._weakest_link_reason(weakest, affected),
        )

    @staticmethod
    def _assumption_reason(conclusion_ids: list[str]) -> str:
        joined = "、".join(conclusion_ids)
        return f"该假设位于通向结论 {joined} 的依赖链上；删除后这些结论会失去一项明确依赖。"

    @staticmethod
    def _weakest_link_reason(claim: Claim, conclusion_ids: list[str]) -> str:
        affected = "、".join(conclusion_ids)
        return (
            f"该声明的证据状态为 {claim.evidence_status.value}，"
            f"且位于通向结论 {affected} 的依赖链上。"
        )
