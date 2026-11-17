"""검색 동의어 사전 — 영/한 용어 불일치를 흡수한다.

한국어 기술 글은 같은 개념을 영문("observability")과 한글("관측성")로 번갈아 쓴다.
검색은 문자열 일치라, 한쪽 표기로 물으면 다른 쪽만 쓴 글에는 닿지 못한다.
실측(2026-11-17, 번들 94편): "관측성"을 쓴 36편 중 13편만 "observability"도 쓴다 —
영문으로 물은 에이전트는 25편을 못 본다.

**수록 기준** — 셋을 모두 만족해야 넣는다. 재측정: `uv run python scripts/synonym_report.py`

1. **이 분야에서 뜻이 같을 것.** 뜻이 겹칠 뿐인 일반어는 넣지 않는다. 넣었다면
   `scope`↔`범위`(94편 중 92편에 등장)·`tracing`↔`추적`(69편, 대개 '추적성')처럼
   재현율이 아니라 잡음만 늘었을 것이다.
2. **양쪽 다 코퍼스에 있을 것.** `resilience`↔`회복탄력성`·`sre`↔`신뢰성 엔지니어링`은
   한글 쪽이 0편이라 아무 일도 하지 않는다.
3. **한쪽 표기로 물었을 때 실제로 놓치는 글이 있을 것.** 약어는 여기서 전부 탈락했다 —
   `검색 증강 생성`을 쓴 9편이 **전부** `rag`도 쓰고, `model context protocol` 22편도
   전부 `mcp`를 쓴다. 약어 확장은 이 코퍼스에서 이득이 0이다.

⚠️ 기준 2의 대가 — **코퍼스에 없지만 사용자는 칠 법한 표기**는 여기서 탈락한다.
`검색증강생성`(붙여쓰기)은 번들에 0번 나오지만 그렇게 물으면 42편을 통째로 놓친다.
질의 쪽 전용 동의어는 분명 쓸모가 있으나, **오타와 구분할 방법이 없어**(`관측셩`도 0편이다)
이번 범위에서는 받지 않는다. 받으려면 '질의 전용' 표를 따로 두고 다르게 검사해야 한다.

**단일 토큰만 수록한다.** 질의는 공백으로 쪼개 term 단위로 매칭하므로, `검색 증강 생성`
같은 구(句)는 3토큰으로 흩어져 묶음에 걸리지 않는다. 구 동의어는 구 매칭이 생긴 뒤의 일이다.

**같은 묶음 안에서 한 변형이 다른 변형의 접두가 되면 안 된다.** 매칭이 선두 경계만
요구해서(`로그를`은 맞고 `블로그`는 아니다) `("auth", "authentication")` 같은 묶음은
`authentication` 한 번을 두 번으로 센다. 가드: `test_no_variant_is_a_prefix_of_another_in_the_same_group`.
"""

from __future__ import annotations

# 각 묶음은 **같은 개념의 다른 표기**다. 순서는 의미가 없다(대칭).
SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    # --- 보안·인가 ---
    ("authentication", "인증"),
    ("authorization", "인가"),
    ("delegation", "위임"),
    ("encryption", "암호화"),
    ("secret", "시크릿"),
    ("audit", "감사"),
    ("security", "보안"),
    # --- RAG·LLM ---
    ("embedding", "임베딩"),
    ("vector", "벡터"),
    ("chunking", "청킹"),
    ("prompt", "프롬프트"),
    ("token", "토큰"),
    # --- AI Agent·MCP ---
    ("agent", "에이전트"),
    ("tool", "도구"),
    ("schema", "스키마"),
    ("orchestration", "오케스트레이션"),
    ("streaming", "스트리밍"),
    # --- 운영·관측 ---
    ("observability", "관측성"),
    ("monitoring", "모니터링"),
    ("logging", "로깅"),
    ("latency", "지연"),
    ("throughput", "처리량"),
    ("capacity", "용량"),
    ("reliability", "신뢰성"),
    ("cache", "캐시"),
    # --- 릴리스·아키텍처 ---
    ("rollback", "롤백"),
    ("canary", "카나리"),
    ("pipeline", "파이프라인"),
    ("governance", "거버넌스"),
    ("architecture", "아키텍처"),
)


def _build_lookup(groups: tuple[tuple[str, ...], ...]) -> dict[str, tuple[str, ...]]:
    """변형 → 그 변형이 속한 묶음. 같은 변형이 두 묶음에 있으면 거부한다.

    한 변형이 두 개념에 걸치면 어느 쪽으로 넓힐지가 사전 순서에 좌우돼
    조용히 엉뚱한 결과를 낸다. 모호한 사전은 자동으로 고를 것이 아니라 고쳐야 한다.
    """
    lookup: dict[str, tuple[str, ...]] = {}
    for group in groups:
        for variant in group:
            if variant in lookup:
                raise ValueError(
                    f"동의어 {variant!r}가 두 묶음에 중복됩니다: {lookup[variant]} / {group}"
                )
            lookup[variant] = group
    return lookup


_LOOKUP = _build_lookup(SYNONYM_GROUPS)


def expand(term: str) -> tuple[str, ...]:
    """질의어 하나를 같은 개념의 표기 묶음으로 넓힌다. 사전에 없으면 자기 자신만."""
    return _LOOKUP.get(term, (term,))


def variants() -> frozenset[str]:
    """사전에 등록된 모든 표기(테스트·리포트용)."""
    return frozenset(_LOOKUP)
