"""구(句) 매칭 테스트.

띄어 쓴 다중어 질의는 낱말 둘로 쪼개져 둘이 **흩어져 있는** 글까지 올린다.
실측(구 도입 전): "감사 로그"류 31개 중 구를 담은 글이 전부 최상위인 경우는 **3건뿐**이었다.

구는 **필터가 아니라 BM25의 추가 항**이다. 구성 낱말보다 희귀하므로 IDF가 저절로 큰
가중치를 준다 — 임의의 보너스 상수가 없다. 빈도를 더하기만 하므로 **점수를 잃는 글이 없다.**
"""

from __future__ import annotations

import re

import pytest

from aiarchitect_blog_mcp import corpus as corpus_mod
from aiarchitect_blog_mcp.synonyms import expand
from aiarchitect_blog_mcp.corpus import (
    MAX_SEARCH_LIMIT,
    Corpus,
    _adjacent_phrases,
    _term_count,
)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus()


def _haystack(corpus: Corpus, record: dict) -> str:
    return (
        f"{record['title']} {' '.join(record['tags'])} {record['description']} "
        f"{corpus._body(record)}"
    ).lower()


def _owners(corpus: Corpus, phrase: str) -> set[str]:
    """구를 통째로 담은 글."""
    return {r["id"] for r in corpus.records if _term_count(_haystack(corpus, r), phrase)}


# --- 구를 만드는 규칙 ---

def test_phrases_are_adjacent_pairs_only():
    """붙여 쓴 말만 구로 본다 — 떨어진 쌍("a c")은 구가 아니다."""
    assert _adjacent_phrases(["a", "b", "c"]) == (("a b",), ("b c",))
    assert _adjacent_phrases(["a"]) == ()
    assert _adjacent_phrases([]) == ()


def test_repeated_pairs_are_counted_once():
    """같은 쌍이 두 번 나와도 개념은 하나다 — 따로 세면 이중 가산된다."""
    assert _adjacent_phrases(["a", "b", "a", "b"]) == (("a b",), ("b a",))


# --- 핵심 동작 ---

def test_documents_containing_the_phrase_rank_first(corpus: Corpus):
    """구를 통째로 담은 글이 낱말만 흩어진 글보다 앞서야 한다."""
    for phrase in ("감사 로그", "최소 권한", "도구 호출"):
        owners = _owners(corpus, phrase)
        assert owners, f"{phrase!r}를 담은 글이 없다 — 이 테스트의 전제가 깨졌다"
        ranked = [r["id"] for r in corpus.search(phrase, limit=MAX_SEARCH_LIMIT)]
        top = set(ranked[: len(owners)])
        assert top == owners, (
            f"{phrase!r}: 구를 담은 글 {sorted(owners)}가 최상위에 모이지 않았다 → {ranked[:len(owners)]}"
        )


def test_phrase_is_a_bonus_not_a_filter(corpus: Corpus):
    """구를 담지 않아도 낱말이 맞으면 여전히 결과에 남는다 — 재현율을 깎지 않는다."""
    owners = _owners(corpus, "감사 로그")
    results = [r["id"] for r in corpus.search("감사 로그", limit=MAX_SEARCH_LIMIT)]
    assert len(results) > len(owners), "구가 필터처럼 동작해 결과가 구 보유 글로 좁혀졌다"


def _scored_ids(corpus: Corpus, query: str, *, with_phrases: bool) -> set[str]:
    """점수가 0보다 큰 글 전체 — `limit` 상한을 우회한다.

    🔴 `search(limit=MAX_SEARCH_LIMIT)`로 비교하면 안 된다. 상한이 50인데 흔한 질의는
    80편 넘게 점수를 받아 **잘린다.** 잘린 것을 "잃었다"고 읽으면 틀린 결론이 나온다
    (실제로 이 테스트를 그렇게 썼다가 한 번 헛돌았다).
    """
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    concepts = tuple(dict.fromkeys(expand(t) for t in terms))
    if with_phrases:
        concepts += _adjacent_phrases(terms)
    return {r["id"] for r in corpus.records if any(corpus._concept_tf(r, c) for c in concepts)}


def test_no_document_loses_its_score(corpus: Corpus):
    """🔬 안전성: 구는 빈도를 **더하기만** 한다 — 점수를 받던 글이 사라지지 않는다.

    순위는 바뀌어도 집합은 그대로여야 한다. 이것이 성립하면 구 매칭은 재현율을
    깎을 수 없다 — 노출 순서만 바꾼다.
    """
    for query in ("감사 로그", "MCP OAuth", "RAG 청킹", "관측성 설계", "최소 권한 설계"):
        before = _scored_ids(corpus, query, with_phrases=False)
        after = _scored_ids(corpus, query, with_phrases=True)
        assert not (before - after), (
            f"{query!r}: 구 매칭 때문에 점수를 잃은 글 {sorted(before - after)}"
        )
        assert after >= before


def test_disabling_phrases_breaks_the_ranking(corpus: Corpus, monkeypatch):
    """절제 실험: 구를 끄면 위 순위 테스트가 **실패해야** 한다.

    끄고도 통과한다면 그 테스트는 구 매칭을 전혀 검사하지 않는 것이다.
    """
    phrase = "감사 로그"
    owners = _owners(corpus, phrase)
    assert set([r["id"] for r in corpus.search(phrase, limit=MAX_SEARCH_LIMIT)][: len(owners)]) == owners

    monkeypatch.setattr(corpus_mod, "_adjacent_phrases", lambda terms: ())
    plain = Corpus()
    ranked = [r["id"] for r in plain.search(phrase, limit=MAX_SEARCH_LIMIT)]
    assert set(ranked[: len(owners)]) != owners, (
        "구를 껐는데도 구 보유 글이 최상위에 모인다 — 순위 테스트가 구를 검사하지 않는다"
    )


def test_single_token_query_is_unchanged(corpus: Corpus, monkeypatch):
    """한 낱말 질의에는 구가 없다 — 기존 동작이 그대로여야 한다."""
    before = [r["id"] for r in corpus.search("관측성", limit=20)]
    monkeypatch.setattr(corpus_mod, "_adjacent_phrases", lambda terms: ())
    assert [r["id"] for r in Corpus().search("관측성", limit=20)] == before


# --- 가중치가 상수가 아니라 IDF에서 온다 ---

def test_rarer_phrases_lift_more_than_common_ones(corpus: Corpus, monkeypatch):
    """구의 무게는 **희귀도**에서 온다 — 모든 구에 같은 보너스를 주는 것이 아니다.

    흔한 구와 희귀한 구의 점수 상승폭이 같다면, 어딘가에 상수가 박혀 있다는 뜻이다.
    """
    def lift(query: str) -> float:
        with_phrase = corpus.search(query, limit=1)[0]["score"]
        monkeypatch.setattr(corpus_mod, "_adjacent_phrases", lambda terms: ())
        without = Corpus().search(query, limit=1)[0]["score"]
        monkeypatch.undo()
        return with_phrase - without

    rare, common = lift("스키마 검증"), lift("보안 설계")
    assert rare > 0 and common >= 0
    assert rare != common, "희귀한 구와 흔한 구의 상승폭이 같다 — 상수 보너스가 박혀 있다"


# --- 경계 규칙은 그대로 ---

def test_phrase_matching_keeps_the_leading_boundary_rule():
    """구도 낱말 가운데서 시작하면 안 된다."""
    assert _term_count("감사 로그를 남긴다", "감사 로그") == 1
    assert _term_count("내부감사 로그를 남긴다", "감사 로그") == 0


def test_phrase_is_literal_not_expanded_by_synonyms(corpus: Corpus):
    """구는 쓴 그대로 센다. 표기 조합까지 펼치면 경우의 수가 폭발한다.

    낱말 단위 개념 점수가 이미 동의어를 처리하므로, 구까지 넓힐 이유가 없다.
    """
    phrases = _adjacent_phrases(["관측성", "설계"])
    assert phrases == (("관측성 설계",),), f"구가 동의어로 넓혀졌다: {phrases}"
