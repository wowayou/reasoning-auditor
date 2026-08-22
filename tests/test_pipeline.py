import json

from auditor.pipeline import AuditPipeline
from auditor.providers import DemoMockProvider, ProviderError


def test_pipeline_runs_end_to_end_with_demo_provider() -> None:
    provider = DemoMockProvider()

    report = AuditPipeline(provider).run("未来 B2B 增长会转向 ABM")

    assert report.graph.original_text == "未来 B2B 增长会转向 ABM"
    assert len(report.graph.claims) == 3
    assert report.analysis.load_bearing_assumptions[0].claim_id == "c2"
    assert [item.content for item in report.alternatives] == ["季节性波动"]
    assert report.rhetoric.flags == []
    assert report.rhetoric.risk == "LOW"
    assert len(report.verification_steps) == 1
    assert len(provider.calls) == 2


def test_pipeline_scans_rhetorical_amplification() -> None:
    provider = DemoMockProvider()

    report = AuditPipeline(provider).run("SEO 正在死亡，企业必须全面转向 ABM")

    assert report.rhetoric.flags == ["正在死亡", "必须", "全面"]
    assert report.rhetoric.risk == "HIGH"


def test_pipeline_can_skip_alternative_provider_call() -> None:
    provider = DemoMockProvider()

    report = AuditPipeline(provider).run("观点", include_alternatives=False)

    assert report.alternatives == []
    assert len(provider.calls) == 1


def test_pipeline_reports_stage_progress() -> None:
    events: list[str] = []
    AuditPipeline(DemoMockProvider()).run("观点", on_stage=events.append)

    assert events == ["decompose", "analyze", "rhetoric", "alternatives", "verification", "report"]


def test_pipeline_stage_progress_skips_disabled_alternatives() -> None:
    events: list[str] = []
    AuditPipeline(DemoMockProvider()).run(
        "观点", include_alternatives=False, on_stage=events.append
    )

    assert "alternatives" not in events


def test_pipeline_repair_keeps_total_provider_calls_within_three() -> None:
    class RepairingProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def complete(self, prompt: str) -> str:
            self.calls.append(prompt)
            if len(self.calls) == 1:
                return "not json"
            if "修复下面的 ClaimGraph JSON" in prompt:
                return json.dumps(
                    {
                        "compressed_view": "观点",
                        "claims": [{"id": "c1", "type": "OBS", "content": "观察"}],
                        "edges": [],
                    }
                )
            return "[]"

    provider = RepairingProvider()
    report = AuditPipeline(provider).run("观点", include_alternatives=True)

    assert report.graph.claims[0].content == "观察"
    assert len(provider.calls) == 3


def test_pipeline_keeps_core_report_when_alternative_provider_call_fails() -> None:
    class AlternativeFailureProvider(DemoMockProvider):
        def complete(self, prompt: str) -> str:
            if "针对下面的 ClaimGraph" in prompt:
                raise ProviderError("provider request timed out")
            return super().complete(prompt)

    report = AuditPipeline(AlternativeFailureProvider()).run("观点")

    assert report.graph.claims
    assert report.alternatives == []
    assert report.warnings == [
        "替代解释调用失败，但声明图已保留；本次报告已跳过替代解释。"
    ]
