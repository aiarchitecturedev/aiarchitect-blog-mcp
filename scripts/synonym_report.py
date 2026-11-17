#!/usr/bin/env python3
"""동의어 사전 ↔ 번들 코퍼스 측정 리포트.

`synonyms.py`의 수록 기준은 숫자로 정해진다 — "한쪽 표기로 물었을 때 실제로 놓치는 글이
몇 편인가". 그 숫자는 코퍼스가 자라면 바뀌므로 **소스에 박아 두지 않고 여기서 뽑는다.**

출력의 `이득`은 **그 표기로 물었을 때 확장이 새로 닿게 해 주는 글 수**다.
`observability` 13편 / `관측성` 36편 / 합집합 38편이면, 영문으로 물을 때의 이득은 25편이다.

사용:
    python scripts/synonym_report.py                  # 현재 사전 측정
    python scripts/synonym_report.py canary:카나리 ...  # 후보 쌍을 넣기 전에 평가

종료 코드: 0 정상 · 1 문제 발견(코퍼스에 없는 변형, 이득 0인 묶음) · 2 코퍼스 없음
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from aiarchitect_blog_mcp.corpus import Corpus  # noqa: E402
from aiarchitect_blog_mcp.synonyms import SYNONYM_GROUPS  # noqa: E402


def _docs_with(corpus: Corpus, term: str) -> set[str]:
    return {r["id"] for r in corpus.records if corpus._weighted_tf(r, term) > 0}


def _display_width(text: str) -> int:
    """한글은 터미널에서 두 칸을 먹는다 — 표를 맞추려면 글자 수가 아니라 폭으로 센다."""
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)


def _pair_label(group: tuple[str, ...], per: dict[str, set[str]]) -> str:
    return " ↔ ".join(f"{v}({len(per[v])})" for v in group)


def report(corpus: Corpus, groups: tuple[tuple[str, ...], ...], label: str) -> int:
    total = len(corpus.records)
    print(f"\n{label} — 번들 {total}편 기준")
    print("괄호 안은 그 표기가 나오는 글 수, +N은 그 표기로 물을 때 확장이 새로 닿는 글 수\n")

    problems: list[str] = []
    rows = []
    for group in groups:
        per = {v: _docs_with(corpus, v) for v in group}
        union = set().union(*per.values()) if per else set()
        gains = {v: len(union) - len(ids) for v, ids in per.items()}
        best = max(gains.values()) if gains else 0
        rows.append((best, group, per, union, gains))

        dead = [v for v, ids in per.items() if not ids]
        if dead:
            problems.append(f"코퍼스에 없는 변형 {dead} (묶음 {group}) — 오타이거나 사어")
        elif best == 0:
            problems.append(f"이득 0인 묶음 {group} — 한 표기가 다른 표기를 완전히 포함한다")

    width = max((_display_width(_pair_label(g, p)) for _, g, p, _, _ in rows), default=20)
    for best, group, per, union, gains in sorted(rows, key=lambda r: -r[0]):
        label_text = _pair_label(group, per)
        pad = " " * max(0, width - _display_width(label_text))
        detail = " · ".join(f"{v} +{gains[v]}" for v in group)
        print(f"{'  ' if best else '⚠️'}{label_text}{pad}   합집합 {len(union):>3}편   {detail}")

    if problems:
        print("\n문제:")
        for p in problems:
            print(f"  ❌ {p}")
        return 1
    print(f"\n✅ {len(groups)}개 묶음 전부 유효 (변형이 코퍼스에 존재하고 이득 > 0)")
    return 0


def _parse(args: list[str]) -> tuple[tuple[str, ...], ...]:
    groups = []
    for arg in args:
        parts = tuple(p.strip().lower() for p in arg.split(":") if p.strip())
        if len(parts) < 2:
            raise SystemExit(f"❌ 쌍 형식이 아님: {arg!r} (예: canary:카나리)")
        groups.append(parts)
    return tuple(groups)


def main(argv: list[str]) -> int:
    try:
        corpus = Corpus()
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if argv:
        return report(corpus, _parse(argv), "후보 평가")
    return report(corpus, SYNONYM_GROUPS, "수록된 동의어 묶음")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
