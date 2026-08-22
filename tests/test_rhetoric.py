import pytest

from auditor.detectors.rhetoric import RhetoricScanner


def test_scanner_detects_unique_rhetorical_terms_in_stable_order() -> None:
    result = RhetoricScanner().scan("这是新时代的革命性范式，必然颠覆所有市场。")

    assert result.flags == ["新时代", "革命性", "范式", "必然", "颠覆", "所有"]
    assert result.risk == "HIGH"


def test_scanner_marks_clean_text_as_low_without_claiming_truth() -> None:
    result = RhetoricScanner().scan("本季度转化率较上季度下降 8%。")

    assert result.flags == []
    assert result.risk == "LOW"


def test_scanner_ignores_explicit_negation_and_counterexample_language() -> None:
    result = RhetoricScanner().scan("这不是必然结果，也并非唯一解释，不一定会颠覆市场。")

    assert result.flags == []
    assert result.risk == "LOW"


@pytest.mark.parametrize("text", ["", "   ", None])
def test_scanner_rejects_empty_text(text: str | None) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        RhetoricScanner().scan(text)  # type: ignore[arg-type]
