"""AI Reasoning Auditor core package."""

from auditor.schema import AuditReport, Claim, ClaimEdge, ClaimGraph
from auditor.stages import AlternativeStage, DecomposeStage
from auditor.pipeline import AuditPipeline
from auditor.detectors import RhetoricScanner
from auditor.verification import VerificationPlanner
from auditor.providers import OpenAICompatibleProvider, ProviderError

__all__ = [
    "AlternativeStage",
    "AuditPipeline",
    "AuditReport",
    "Claim",
    "ClaimEdge",
    "ClaimGraph",
    "DecomposeStage",
    "RhetoricScanner",
    "VerificationPlanner",
    "OpenAICompatibleProvider",
    "ProviderError",
]
