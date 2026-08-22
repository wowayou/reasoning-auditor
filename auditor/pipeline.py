"""Small, explicit orchestration layer for the acceptance MVP."""

from __future__ import annotations

from collections.abc import Callable

from auditor.detectors.rhetoric import RhetoricScanner
from auditor.graph.ops import GraphAnalyzer
from auditor.providers import Provider, ProviderError
from auditor.schema import AuditReport, CurrentJudgement, ClaimType
from auditor.stages.alternatives import AlternativeError, AlternativeStage
from auditor.stages.decompose import DecomposeStage
from auditor.verification import VerificationPlanner


class AuditPipeline:
    """Run decomposition, structural analysis, and alternatives in order."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.decompose = DecomposeStage(provider)
        self.alternatives = AlternativeStage(provider)
        self.analyzer = GraphAnalyzer()
        self.rhetoric = RhetoricScanner()
        self.verification = VerificationPlanner()

    def run(
        self,
        text: str,
        *,
        include_alternatives: bool = True,
        on_stage: Callable[[str], None] | None = None,
    ) -> AuditReport:
        def stage(name: str) -> None:
            if on_stage is not None:
                on_stage(name)

        stage("decompose")
        graph = self.decompose.run(text)
        stage("analyze")
        analysis = self.analyzer.analyze(graph)
        stage("rhetoric")
        rhetoric = self.rhetoric.scan(graph.original_text)
        if include_alternatives:
            stage("alternatives")
            try:
                alternatives = self.alternatives.run(graph)
            except (AlternativeError, ProviderError):
                alternatives = []
                self.alternatives.warning = (
                    "替代解释调用失败，但声明图已保留；本次报告已跳过替代解释。"
                )
        else:
            alternatives = []
        stage("verification")
        verification_steps = self.verification.plan(graph, analysis)
        stage("report")
        warnings = [self.alternatives.warning] if self.alternatives.warning else []

        return AuditReport(
            graph=graph,
            analysis=analysis,
            rhetoric=rhetoric,
            alternatives=alternatives,
            verification_steps=verification_steps,
            warnings=warnings,
            judgement=CurrentJudgement(
                reasonable_insights=[
                    claim.content
                    for claim in graph.claims
                    if claim.type is ClaimType.OBS
                ],
                unverified_extrapolations=[
                    claim.content
                    for claim in graph.claims
                    if claim.type is not ClaimType.OBS
                ],
            ),
        )
