import json

from auditor.graph.ops import GraphAnalyzer
from auditor.render import JSONReportRenderer
from auditor.schema import AuditReport, Claim, ClaimGraph, ClaimType


def test_json_renderer_is_machine_readable_and_preserves_report_contract() -> None:
    graph = ClaimGraph(
        original_text="观点",
        compressed_view="压缩观点",
        claims=[Claim(id="c1", type=ClaimType.OBS, content="观察")],
    )
    report = AuditReport(graph=graph, analysis=GraphAnalyzer().analyze(graph))

    payload = json.loads(JSONReportRenderer().render(report))

    assert payload["graph"]["original_text"] == "观点"
    assert payload["graph"]["claims"][0]["type"] == "OBS"
    assert payload["analysis"]["reasoning_chains"][0]["claim_ids"] == ["c1"]
