"""Deterministic planning of small validation experiments."""

from __future__ import annotations

from auditor.schema import ClaimGraph, GraphAnalysis, VerificationStep


class VerificationPlanner:
    """Turn structural weak points into bounded, non-decisive next steps."""

    def plan(self, graph: ClaimGraph, analysis: GraphAnalysis) -> list[VerificationStep]:
        claims_by_id = {claim.id: claim for claim in graph.claims}
        steps: list[VerificationStep] = []
        for assumption in analysis.load_bearing_assumptions[:3]:
            claim = claims_by_id[assumption.claim_id]
            steps.append(
                VerificationStep(
                    experiment=f"针对“{claim.content}”做小样本对照验证，先确认它是否解释观察到的变化。",
                    cost="低到中",
                    duration="1-2 周",
                )
            )

        if not steps and analysis.weakest_link:
            claim = claims_by_id[analysis.weakest_link.claim_id]
            steps.append(
                VerificationStep(
                    experiment=f"为“{claim.content}”建立一个可重复的基线测量。",
                    cost="低",
                    duration="1 周",
                )
            )
        return steps
