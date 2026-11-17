#!/usr/bin/env python3
"""동의어 사전 ↔ 번들 코퍼스 측정 리포트.

`synonyms.py`의 수록 기준은 숫자로 정해진다 — "한쪽 표기로 물었을 때 실제로 놓치는 글이
몇 편인가". 그 숫자는 코퍼스가 자라면 바뀌므로 **소스에 박아 두지 않고 여기서 뽑는다.**

출력의 `이득`은 **그 표기로 물었을 때 확장이 새로 닿게 해 주는 글 수**다.
`observability` 13편 / `관측성` 36편 / 합집합 38편이면, 영문으로 물을 때의 이득은 25편이다.

두 표를 **반대 기준**으로 잰다. `SYNONYM_GROUPS`의 표기는 코퍼스에 **있어야** 하고,
`QUERY_FORMS`(붙여 쓴 질의형)의 키는 **없어야** 하며 띄어 쓴 형태가 코퍼스에 있어야 한다
— 그것이 오타(`관측셩`)와 정당한 붙여쓰기(`검색증강생성`)를 가르는 유일한 기계적 수단이다.

사용:
    python scripts/synonym_report.py                  # 두 표 전부 측정
    python scripts/synonym_report.py canary:카나리 ...  # 동의어 후보 쌍 평가
    python scripts/synonym_report.py --query 검색증강생성:rag ...   # 질의형 후보 평가

종료 코드: 0 정상 · 1 문제 발견 · 2 코퍼스 없음
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from aiarchitect_blog_mcp.corpus import Corpus, has_spaced_variant  # noqa: E402
from aiarchitect_blog_mcp.synonyms import (  # noqa: E402
    QUERY_FORMS,
    SYNONYM_GROUPS,
    expand,
)


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


def report_query_forms(corpus: Corpus, table: dict[str, tuple[str, ...]]) -> int:
    """질의 전용 표기 측정 — 키는 없어야 하고, 도출돼야 하고, 대상은 있어야 한다."""
    text = "\n".join(
        f"{r['title']} {' '.join(r['tags'])} {r['description']} {corpus._lower_body(r)}".lower()
        for r in corpus.records
    )
    nospace = re.sub(r"\s+", "", text)

    print(f"\n질의 전용 표기(띄어쓰기) — 번들 {len(corpus.records)}편 기준")
    print("키는 지금 0편이다. 화살표 뒤가 넓힌 뒤 닿는 글 수\n")

    problems: list[str] = []
    rows = []
    for key, targets in table.items():
        hits = _docs_with(corpus, key)
        derivable = has_spaced_variant(text, key)
        reach: set[str] = set()
        for target in targets:
            for variant in expand(target):
                reach |= _docs_with(corpus, variant)
        rows.append((len(reach), key, targets, hits, derivable))

        if hits:
            problems.append(
                f"{key!r}가 코퍼스에 {len(hits)}편 등장 — 질의 전용이 아닌 진짜 표기다. "
                f"SYNONYM_GROUPS로 옮길 것"
            )
        elif not derivable:
            problems.append(
                f"{key!r}는 띄어 쓴 형태조차 코퍼스에 없다 — 오타이거나 근거 없는 의미 분해"
            )
        elif not reach:
            problems.append(f"{key!r} → {targets}: 대상이 0편이다")

    width = max((_display_width(k) for _, k, _, _, _ in rows), default=12)
    for reach_n, key, targets, hits, derivable in sorted(rows, key=lambda r: -r[0]):
        pad = " " * max(0, width - _display_width(key))
        mark = "  " if not hits and derivable and reach_n else "⚠️"
        print(f"{mark}{key}{pad}  0편 → {reach_n:>3}편   대상: {' / '.join(targets)}")

    if problems:
        print("\n문제:")
        for problem in problems:
            print(f"  ❌ {problem}")
        return 1
    print(f"\n✅ {len(table)}개 항목 전부 유효 (키는 0편·도출 가능, 대상은 코퍼스에 존재)")
    return 0


def _parse_query_forms(args: list[str]) -> dict[str, tuple[str, ...]]:
    table: dict[str, tuple[str, ...]] = {}
    for arg in args:
        key, _, rest = arg.partition(":")
        targets = tuple(t.strip().lower() for t in rest.split(",") if t.strip())
        if not key.strip() or not targets:
            raise SystemExit(f"❌ 형식이 아님: {arg!r} (예: 검색증강생성:rag)")
        table[key.strip().lower()] = targets
    return table


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

    if "--query" in argv:
        rest = [a for a in argv if a != "--query"]
        return report_query_forms(corpus, _parse_query_forms(rest))
    if argv:
        return report(corpus, _parse(argv), "후보 평가")
    return report(corpus, SYNONYM_GROUPS, "수록된 동의어 묶음") or report_query_forms(
        corpus, QUERY_FORMS
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
