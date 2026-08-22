from auditor.graph.ops import GraphAnalyzer
from auditor.render import MarkdownReportRenderer
from auditor.schema import (
    AuditReport,
    Claim,
    ClaimEdge,
    ClaimGraph,
    ClaimType,
    CurrentJudgement,
    RhetoricAssessment,
    VerificationStep,
    AlternativeExplanation,
)


def test_renderer_emits_fixed_sections_and_claim_table() -> None:
    graph = ClaimGraph(
        original_text="SEO 正在死亡。",
        compressed_view="部分搜索流量变化被外推成 SEO 整体失效。",
        claims=[
            Claim(id="obs", type=ClaimType.OBS, content="部分流量下降。"),
            Claim(
                id="assumption",
                type=ClaimType.ASSUMPTION,
                content="流量下降主要由 AI 搜索导致。",
            ),
            Claim(
                id="recommendation",
                type=ClaimType.RECOMMENDATION,
                content="增加 ABM 投入 | 先做试验。",
            ),
        ],
        edges=[
            ClaimEdge(from_claim_id="obs", to_claim_id="assumption"),
            ClaimEdge(from_claim_id="assumption", to_claim_id="recommendation"),
        ],
    )
    report = AuditReport(
        graph=graph,
        analysis=GraphAnalyzer().analyze(graph),
        rhetoric=RhetoricAssessment(flags=["必然"], risk="HIGH"),
        alternatives=[
            AlternativeExplanation(
                content="算法更新",
                exclusion_method="对比更新时间前后的关键词排名",
                required_data=["GSC 数据"],
                cost="低",
            )
        ],
        judgement=CurrentJudgement(
            reasonable_insights=["部分流量下降。"],
            unverified_extrapolations=["SEO 整体失效。"],
        ),
        verification_steps=[
            VerificationStep(experiment="抽样关键词分析", cost="低", duration="两周")
        ],
    )

    markdown = MarkdownReportRenderer().render(report)

    assert markdown.startswith("# AI观点审计报告")
    for section in (
        "## 原始观点",
        "## 压缩后的真实观点",
        "## 修辞风险",
        "## 声明结构",
        "## 最大承重假设",
        "## 替代解释",
        "## 当前判断",
        "## 下一步验证",
    ):
        assert section in markdown
    assert "| RECOMMENDATION | 增加 ABM 投入 \\| 先做试验。 | NOT_CHECKED |" in markdown
    assert "为什么重要：" in markdown
    assert "最弱环节：" in markdown
    assert "风险等级：HIGH" in markdown


def test_renderer_handles_empty_optional_sections() -> None:
    graph = ClaimGraph(
        original_text="事实",
        compressed_view="事实",
        claims=[Claim(id="obs", type=ClaimType.OBS, content="事实")],
    )
    markdown = MarkdownReportRenderer().render(
        AuditReport(graph=graph, analysis=GraphAnalyzer().analyze(graph))
    )

    assert "当前阶段未执行修辞扫描。" in markdown
    assert "当前阶段未提供替代解释。" in markdown
    assert "当前阶段未提供验证实验。" in markdown


def test_renderer_includes_non_fatal_audit_warnings() -> None:
    graph = ClaimGraph(
        original_text="事实",
        compressed_view="事实",
        claims=[Claim(id="obs", type=ClaimType.OBS, content="事实")],
    )
    markdown = MarkdownReportRenderer().render(
        AuditReport(
            graph=graph,
            analysis=GraphAnalyzer().analyze(graph),
            warnings=["已丢弃 2 条不完整的替代解释。"],
        )
    )

    assert "## 审计提示" in markdown
    assert "已丢弃 2 条不完整的替代解释。" in markdown
