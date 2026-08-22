"""Markdown renderer for audit reports."""

from __future__ import annotations

import json

from auditor.schema import AuditReport, Claim


class MarkdownReportRenderer:
    """Render an AuditReport using the fixed PRD section order."""

    def render(self, report: AuditReport) -> str:
        graph = report.graph
        analysis = report.analysis
        lines = [
            "# AI观点审计报告",
            "",
            "## 原始观点",
            "",
            graph.original_text,
            "",
            "---",
            "",
            "## 压缩后的真实观点",
            "",
            graph.compressed_view,
            "",
            "---",
            "",
            "## 修辞风险",
            "",
        ]
        if report.rhetoric.flags:
            lines.extend(f"* {flag}" for flag in report.rhetoric.flags)
            lines.append(f"\n风险等级：{report.rhetoric.risk}")
        elif report.rhetoric.risk == "NOT_CHECKED":
            lines.append("当前阶段未执行修辞扫描。")
        else:
            lines.append(f"未命中预设修辞词。风险等级：{report.rhetoric.risk}")

        lines.extend(
            [
                "",
                "---",
                "",
                "## 声明结构",
                "",
                "| 类型 | 内容 | 状态 |",
                "| --- | --- | --- |",
            ]
        )
        lines.extend(self._claim_row(claim) for claim in graph.claims)

        lines.extend(["", "---", "", "## 最大承重假设", ""])
        if analysis.load_bearing_assumptions:
            claims_by_id = {claim.id: claim for claim in graph.claims}
            for index, assumption in enumerate(analysis.load_bearing_assumptions, 1):
                lines.extend(
                    [
                        f"{index}. {self._plain(claims_by_id[assumption.claim_id].content)}",
                        "",
                        f"为什么重要：{assumption.reason}",
                        "",
                    ]
                )
        else:
            lines.append("未识别到连接主要结论的隐藏假设。\n")

        if analysis.weakest_link:
            weakest_claim = next(
                claim
                for claim in graph.claims
                if claim.id == analysis.weakest_link.claim_id
            )
            lines.extend(
                [
                    f"最弱环节：{weakest_claim.content}",
                    "",
                    analysis.weakest_link.reason,
                    "",
                ]
            )

        lines.extend(["---", "", "## 替代解释", ""])
        if report.alternatives:
            for index, alternative in enumerate(report.alternatives, 1):
                lines.extend(
                    [
                        f"{index}. {alternative.content}",
                        "",
                        f"排除方法：{alternative.exclusion_method}",
                        "",
                        f"需要数据：{', '.join(alternative.required_data)}",
                        "",
                        f"成本：{alternative.cost}",
                        "",
                    ]
                )
        else:
            lines.append("当前阶段未提供替代解释。\n")

        lines.extend(["---", "", "## 当前判断", "", "```", "合理洞察："])
        lines.extend(f"{item}" for item in report.judgement.reasonable_insights)
        lines.extend(["", "未经验证外推："])
        lines.extend(f"{item}" for item in report.judgement.unverified_extrapolations)
        lines.extend(["```", "", "---", "", "## 下一步验证", ""])
        if report.verification_steps:
            for index, step in enumerate(report.verification_steps, 1):
                lines.extend(
                    [
                        f"{index}. 实验：{step.experiment}",
                        f"成本：{step.cost}",
                        f"周期：{step.duration}",
                        "",
                    ]
                )
        else:
            lines.append("当前阶段未提供验证实验。")

        if report.warnings:
            lines.extend(["", "---", "", "## 审计提示", ""])
            lines.extend(f"* {warning}" for warning in report.warnings)

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _claim_row(claim: Claim) -> str:
        return (
            f"| {claim.type.value} | {MarkdownReportRenderer._cell(claim.content)} | "
            f"{claim.evidence_status.value} |"
        )

    @staticmethod
    def _cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    @staticmethod
    def _plain(value: str) -> str:
        return value.replace("\n", " ")


class JSONReportRenderer:
    """Render the same report contract for machines and downstream tooling."""

    def render(self, report: AuditReport) -> str:
        return json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ) + "\n"
