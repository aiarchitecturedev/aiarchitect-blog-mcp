"""동의어 사전 + 개념 단위 검색 테스트.

사전은 **조용히 썩는다** — 한글 변형에 오타가 나도, 코퍼스에서 용어가 사라져도
검색은 예전처럼 동작하고 아무도 모른다. 그래서 여기서는 사전의 모양만이 아니라
"각 묶음이 실제로 일을 하고 있는가"를 번들 코퍼스에 대고 검사한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from aiarchitect_blog_mcp import corpus as corpus_mod
from aiarchitect_blog_mcp.corpus import Corpus, _term_count
from aiarchitect_blog_mcp.synonyms import (
    SYNONYM_GROUPS,
    _build_lookup,
    expand,
    variants,
)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus()


def _doc_ids_containing(corpus: Corpus, term: str) -> set[str]:
    """term이 (제목·태그·설명·본문 어디든) 나오는 글 id 집합."""
    return {r["id"] for r in corpus.records if corpus._weighted_tf(r, term) > 0}


# --- 사전의 모양 ---

def test_groups_have_at_least_two_variants():
    """변형이 하나뿐인 묶음은 아무것도 넓히지 않는다(사전에 남은 찌꺼기)."""
    assert SYNONYM_GROUPS, "사전이 비어 있다"
    singles = [g for g in SYNONYM_GROUPS if len(set(g)) < 2]
    assert not singles, f"변형이 둘 미만인 묶음: {singles}"


def test_variants_are_single_lowercase_tokens():
    """질의는 소문자화 후 공백으로 쪼개진다 — 대문자·공백이 든 변형은 영원히 안 걸린다."""
    bad = [v for v in variants() if v != v.lower().strip() or not v or " " in v or "\t" in v]
    assert not bad, f"소문자 단일 토큰이 아닌 변형: {bad} (질의 토큰화와 어긋나 죽은 항목이 된다)"


def test_no_variant_is_a_prefix_of_another_in_the_same_group():
    """같은 묶음 안의 접두 중복은 **같은 글자를 두 번 센다**.

    매칭이 선두 경계만 요구하므로 `("auth", "authentication")` 묶음에서는
    "authentication" 한 번이 두 변형 모두에 걸리고, 개념 빈도 합이 2가 된다.
    """
    for group in SYNONYM_GROUPS:
        for a in group:
            for b in group:
                if a != b and b.startswith(a):
                    pytest.fail(f"{a!r}가 {b!r}의 접두다 — 묶음 {group}에서 빈도가 이중 계산된다")


def test_prefix_overlap_really_would_double_count(corpus: Corpus):
    """절제: 위 가드가 막는 상황이 실제로 이중 계산을 내는지 확인한다.

    가드가 **무엇을 막는지** 보이지 않으면, 규칙만 남고 이유는 잊힌다.
    """
    rec = next(r for r in corpus.records if corpus._weighted_tf(r, "authentication") > 0)
    honest = corpus._weighted_tf(rec, "authentication")
    inflated = corpus._concept_tf(rec, ("auth", "authentication"))
    assert inflated > honest, "접두 중복이 이중 계산을 내지 않는다 — 가드의 전제가 틀렸다"


def test_duplicate_variant_across_groups_is_rejected():
    """한 변형이 두 개념에 걸치면 어느 쪽으로 넓힐지가 사전 순서에 좌우된다 — 거부해야 한다."""
    with pytest.raises(ValueError, match="중복"):
        _build_lookup((("cache", "캐시"), ("buffer", "캐시")))


def test_unknown_term_expands_to_itself():
    assert expand("kubernetes") == ("kubernetes",)
    assert expand("") == ("",)


def test_expand_is_symmetric_within_a_group():
    """어느 표기로 물어도 같은 묶음이 나와야 한다(사전은 방향이 없다)."""
    for group in SYNONYM_GROUPS:
        assert len({expand(v) for v in group}) == 1, f"{group}: 변형마다 다른 묶음이 나온다"


# --- 사전이 코퍼스에서 실제로 일하는가 ---

def test_every_variant_occurs_in_the_bundled_corpus(corpus: Corpus):
    """변형 오타·사어(死語) 가드.

    `관측셩`처럼 한 글자만 틀려도 사전은 조용히 아무 일도 하지 않는다. 번들에 한 번도
    안 나오는 변형은 오타이거나, 코퍼스가 바뀌어 더는 쓰이지 않는 말이다.
    """
    missing = sorted(v for v in variants() if not _doc_ids_containing(corpus, v))
    assert not missing, (
        f"번들 94편에 한 번도 안 나오는 변형: {missing} — 오타이거나 사어다. "
        f"재측정: uv run python scripts/synonym_report.py"
    )


def test_every_group_reaches_articles_the_query_spelling_misses(corpus: Corpus):
    """수록 기준 3의 기계적 강제 — 이득이 0인 묶음은 사전에 둘 이유가 없다.

    약어(`rag`↔`검색 증강 생성`)가 여기서 전부 탈락했다. 확장형을 쓴 글이 **전부**
    약어도 쓰기 때문에 넓혀도 새로 닿는 글이 없다.
    """
    for group in SYNONYM_GROUPS:
        union: set[str] = set()
        per_variant = {}
        for v in group:
            per_variant[v] = _doc_ids_containing(corpus, v)
            union |= per_variant[v]
        gain = max(len(union) - len(ids) for ids in per_variant.values())
        assert gain > 0, (
            f"{group}: 어느 표기로 물어도 새로 닿는 글이 없다(이득 0) — 사전에서 빼라"
        )


def test_search_reaches_articles_written_only_in_the_other_spelling(corpus: Corpus):
    """핵심 동작: 영문으로 물어도 한글로만 쓴 글에 닿는다(그 반대도)."""
    results = corpus.search("observability", limit=10)
    ids = {r["id"] for r in results}
    korean_only = _doc_ids_containing(corpus, "관측성") - _doc_ids_containing(corpus, "observability")
    assert korean_only, "'관측성'만 쓴 글이 없다 — 이 테스트의 전제가 깨졌다"
    assert ids & korean_only, (
        f"'observability' 검색이 한글 표기만 쓴 글에 닿지 못했다 (후보 {sorted(korean_only)})"
    )


def test_both_spellings_return_the_same_ranking(corpus: Corpus):
    """표기를 바꿔 물었다고 결과가 달라지면 안 된다 — 같은 개념이기 때문이다."""
    for a, b in (("observability", "관측성"), ("canary", "카나리"), ("logging", "로깅")):
        left = [r["id"] for r in corpus.search(a, limit=10)]
        right = [r["id"] for r in corpus.search(b, limit=10)]
        assert left == right, f"{a!r} vs {b!r}: 결과가 다르다\n{left}\n{right}"


def test_same_concept_typed_twice_is_not_double_counted(corpus: Corpus):
    """"observability 관측성"처럼 두 표기를 함께 쳐도 한 번만 센다.

    따로 세면 양쪽 표기를 다 쓴 글이 두 배로 가산돼, 한쪽 표기로만 쓴 글을 부당하게 밀어낸다.
    """
    one = corpus.search("observability", limit=10)
    both = corpus.search("observability 관측성", limit=10)
    assert [r["id"] for r in one] == [r["id"] for r in both]
    assert [r["score"] for r in one] == [r["score"] for r in both], (
        "같은 개념을 두 번 쳤더니 점수가 변했다 — 개념 중복 제거가 동작하지 않는다"
    )


def test_expansion_never_returns_an_article_without_any_variant(corpus: Corpus):
    """정밀도 가드: 넓히더라도 **어느 표기도 없는** 글이 결과에 들어오면 안 된다."""
    for query in ("관측성", "capacity", "롤백", "encryption"):
        group = expand(query)
        for result in corpus.search(query, limit=10):
            rec = corpus._by_id[result["id"]]
            assert any(corpus._weighted_tf(rec, v) > 0 for v in group), (
                f"{query!r} → {result['id']}: 묶음 {group} 중 어느 표기도 없다"
            )


def test_disabling_synonyms_breaks_the_reach(corpus: Corpus, monkeypatch):
    """절제 실험: 확장을 끄면 위 동작 테스트가 **실패해야** 한다.

    이 리포는 "기능을 빼도 통과하는 테스트"에 두 번 당했다(BM25·익명성 스캐너).
    확장을 꺼서 결과가 그대로라면 위 테스트들은 아무것도 지키지 않고 있는 것이다.
    """
    korean_only = _doc_ids_containing(corpus, "관측성") - _doc_ids_containing(corpus, "observability")
    with_synonyms = {r["id"] for r in corpus.search("observability", limit=10)}
    assert with_synonyms & korean_only

    monkeypatch.setattr(corpus_mod, "expand", lambda term: (term,))
    plain = Corpus()
    without = {r["id"] for r in plain.search("observability", limit=10)}
    assert not (without & korean_only), (
        "확장을 껐는데도 한글 전용 글에 닿았다 — 동작 테스트가 동의어를 검사하지 않고 있다"
    )


def test_term_level_matching_is_unchanged_by_expansion():
    """경계 규칙은 그대로다 — 확장은 '어떤 말을 셀지'만 바꾸고 '어떻게 셀지'는 안 바꾼다."""
    assert _term_count("블로그를 운영한다", "로그") == 0
    assert _term_count("로깅을 켠다", "로깅") == 1


# --- 측정 리포트 스크립트 ---
# 모듈 docstring과 위 테스트들의 실패 메시지가 이 스크립트를 가리킨다.
# 스크립트가 깨지면 "재측정하라"는 안내도 같이 깨진다.

_SPEC = importlib.util.spec_from_file_location(
    "synonym_report", Path(__file__).parents[1] / "scripts" / "synonym_report.py"
)
assert _SPEC is not None and _SPEC.loader is not None
report_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(report_mod)


def test_report_passes_on_the_shipped_dictionary(corpus: Corpus, capsys):
    assert report_mod.report(corpus, SYNONYM_GROUPS, "테스트") == 0
    assert "전부 유효" in capsys.readouterr().out


def test_report_flags_a_variant_missing_from_the_corpus(corpus: Corpus, capsys):
    """한 글자 오타(`관측셩`)는 사전을 조용히 무력화한다 — 리포트가 잡아야 한다."""
    assert report_mod.report(corpus, (("observability", "관측셩"),), "테스트") == 1
    assert "관측셩" in capsys.readouterr().out


def test_report_flags_a_group_that_adds_no_reach(corpus: Corpus, capsys):
    """이득 0 = 모든 표기가 정확히 같은 글들에 나온다 — 넓혀도 새로 닿는 글이 없다.

    실제로 그런 쌍은 드물어 같은 표기를 두 번 넣어 그 경로를 태운다.
    """
    assert report_mod.report(corpus, (("mcp", "mcp"),), "테스트") == 1
    assert "이득 0" in capsys.readouterr().out


def test_report_rejects_a_malformed_candidate_pair():
    with pytest.raises(SystemExit, match="쌍 형식"):
        report_mod._parse(["canary"])
