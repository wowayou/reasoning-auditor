"""Rule-based rhetoric amplification scanner.

The scanner is intentionally a warning system, not a truth classifier. A hit
means that a statement deserves decomposition and verification, not that it is
false.
"""

from __future__ import annotations

import re

from auditor.schema import RhetoricAssessment


class RhetoricScanner:
    """Detect absolute, inevitable, or totalizing language in a viewpoint."""

    # Longer phrases win when terms overlap (for example 革命性 should not also
    # report 革命). Final flags are returned in their occurrence order.
    TERMS: tuple[str, ...] = (
        "新时代",
        "正在死亡",
        "大多数",
        "革命性",
        "颠覆性",
        "必然",
        "必须",
        "不一定",
        "唯一",
        "全面",
        "所有",
        "革命",
        "范式",
        "颠覆",
        "一定",
    )
    NEGATION_PREFIXES: tuple[str, ...] = (
        "不是",
        "并非",
        "未必",
        "不一定",
        "不代表",
        "不能说",
        "避免",
    )

    def scan(self, text: str) -> RhetoricAssessment:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        pattern = "|".join(
            re.escape(term) for term in sorted(self.TERMS, key=len, reverse=True)
        )
        flags: list[str] = []
        for match in re.finditer(pattern, text):
            if match.group(0) == "不一定":
                continue
            prefix = text[max(0, match.start() - 8) : match.start()]
            if any(negation in prefix for negation in self.NEGATION_PREFIXES):
                continue
            if match.group(0) not in flags:
                flags.append(match.group(0))

        if not flags:
            risk = "LOW"
        elif len(flags) == 1:
            risk = "MEDIUM"
        else:
            risk = "HIGH"
        return RhetoricAssessment(flags=flags, risk=risk)
