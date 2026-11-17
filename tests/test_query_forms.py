"""질의 전용 표기(띄어쓰기 정규화) 테스트.

`QUERY_FORMS`의 키는 **일부러 코퍼스에 없다.** 그래서 `SYNONYM_GROUPS`를 지키는
"변형이 코퍼스에 있는가" 가드를 쓸 수 없고, 오타(`관측셩`)와 정당한 붙여쓰기
(`검색증강생성`)가 겉보기에 똑같아진다 — 둘 다 0편이다.

여기서 그 둘을 가르는 것은 **도출 가능성**이다. 공백을 지운 코퍼스에서 키가 나오면
그 말은 실제로 쓰이는 말의 다른 띄어쓰기이고, 안 나오면 아무 근거가 없는 문자열이다.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from aiarchitect_blog_mcp import corpus as corpus_mod
from aiarchitect_blog_mcp.corpus import Corpus, _term_count, has_spaced_variant
from aiarchitect_blog_mcp.synonyms import (
    QUERY_FORMS,
    SYNONYM_GROUPS,
    _check_tables_are_disjoint,
    expand,
)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus()


@pytest.fixture(scope="module")
def corpus_text(corpus: Corpus) -> str:
    """검색이 보는 것과 같은 범위(제목·태그·설명·본문)를 한 덩어리로."""
    return "\n".join(
        f"{r['title']} {' '.join(r['tags'])} {r['description']} {corpus._lower_body(r)}".lower()
        for r in corpus.records
    )


def _doc_ids_containing(corpus: Corpus, term: str) -> set[str]:
    return {r["id"] for r in corpus.records if corpus._weighted_tf(r, term) > 0}


# --- 표의 모양 ---

def test_table_is_not_empty():
    assert QUERY_FORMS, "질의 전용 표가 비어 있다"


def test_keys_are_single_lowercase_tokens():
    """질의는 소문자화 후 공백으로 쪼개진다 — 공백이 든 키는 영원히 조회에 안 걸린다."""
    bad = [k for k in QUERY_FORMS if k != k.lower().strip() or not k or re.search(r"\s", k)]
    assert not bad, f"소문자 단일 토큰이 아닌 키: {bad}"


def test_targets_are_not_empty():
    empty = [k for k, v in QUERY_FORMS.items() if not v]
    assert not empty, f"대상이 비어 있는 키: {empty} — 넓혀도 아무 일이 없다"


def test_tables_are_disjoint():
    """가드가 정반대라(있어야 한다 / 없어야 한다) 양쪽에 있는 표기는 반드시 실수다."""
    _check_tables_are_disjoint()


def test_overlapping_tables_are_rejected(monkeypatch):
    """절제: 겹침 검사가 실제로 막는지 — 규칙만 남고 이유가 잊히지 않게."""
    import aiarchitect_blog_mcp.synonyms as syn

    monkeypatch.setitem(syn.QUERY_FORMS, "관측성", ("observability",))
    with pytest.raises(ValueError, match="양쪽에"):
        _check_tables_are_disjoint()


# --- 코퍼스에 대고 거는 가드 ---

def test_keys_currently_reach_nothing(corpus: Corpus):
    """키가 코퍼스에 있으면 이 표의 소관이 아니다 — `SYNONYM_GROUPS`로 가야 한다.

    `화자분리`가 그 경우다(글이 `화자 분리`와 `화자분리`를 둘 다 쓴다). 양쪽 표에서
    규칙이 달라지므로, 코퍼스가 바뀌어 키가 실제 표기가 되면 여기서 걸려야 한다.
    """
    live = sorted(k for k in QUERY_FORMS if _doc_ids_containing(corpus, k))
    assert not live, (
        f"키가 코퍼스에 실제로 등장한다: {live} — 질의 전용이 아니라 진짜 표기다. "
        f"SYNONYM_GROUPS로 옮기고 거기 기준(이득 > 0)으로 다시 재라"
    )


def test_keys_are_derivable_as_a_spaced_form(corpus_text: str):
    """🔴 **오타 가드.** 키를 띄어 쓴 형태가 코퍼스에 실제로 있어야 한다.

    `검색증강생성`은 `검색 증강 생성`으로 쓰여 있지만 `관측셩`은 어떤 띄어쓰기로도 없다.
    "코퍼스에 없다"는 조건만으로는 이 둘이 구분되지 않는다 — 둘 다 0편이기 때문이다.
    """
    undecidable = sorted(k for k in QUERY_FORMS if not has_spaced_variant(corpus_text, k))
    assert not undecidable, (
        f"띄어 쓴 형태조차 코퍼스에 없는 키: {undecidable} — 오타이거나, 근거 없는 "
        f"의미 분해다(`캐시전략` → cache 류). 재측정: scripts/synonym_report.py"
    )


def test_the_derivation_guard_actually_separates_typos(corpus_text: str):
    """절제: 가드가 **구분을 해내는지** 양쪽 사례로 확인한다.

    한쪽만 보면 "통과했다"가 무엇을 뜻하는지 알 수 없다. 정당한 붙여쓰기는 통과하고
    오타는 걸려야 비로소 이 가드가 일하는 것이다.
    """
    assert has_spaced_variant(corpus_text, "검색증강생성"), (
        "정당한 붙여쓰기가 도출되지 않는다 — 가드가 너무 빡빡하다"
    )
    for typo in ("관측셩", "검색증강셍성", "감사로구"):
        assert not has_spaced_variant(corpus_text, typo), (
            f"오타 {typo!r}가 도출돼 버린다 — 가드가 오타를 걸러내지 못한다"
        )


def test_derivation_guard_keeps_word_boundaries(corpus_text: str):
    """🔬 **코퍼스의 공백을 통째로 지우는 방식으로는 이 가드를 만들 수 없다.**

    처음에 그렇게 짰다가 고쳤다. 공백을 지우면 낱말 경계가 사라지고, 그 뒤에 남는
    두 선택지가 **양쪽 다 틀린다**:

      (a) 경계 규칙을 적용하면 — 정당한 도출이 막힌다. "접근 권한 위임"이 "접근권한위임"이
          돼 `권한위임` 앞 글자가 '근'이 되고, 실제로 쓰이는 말이 거부된다.
      (b) 경계 없이 부분문자열로 보면 — 쓰레기가 통과한다. "도구 호출" → "도구호출" 안에서
          `구호출` 같은 낱말 토막이 "도출됐다"고 인정된다.

    원문에서 **띄어 쓴 형태를 찾으면** 경계가 보존돼 둘 다 피한다.
    """
    assert has_spaced_variant(corpus_text, "권한위임"), "정당한 도출이 막혔다"
    assert not has_spaced_variant(corpus_text, "구호출"), (
        "낱말 가운데서 시작하는 토막이 도출로 인정됐다 — 경계가 보존되지 않는다"
    )

    stripped = re.sub(r"\s+", "", corpus_text)
    assert _term_count(stripped, "권한위임") == 0, "(a) 공백 제거 + 경계 규칙이 정당한 도출을 막지 않는다"
    assert "구호출" in stripped, "(b) 공백 제거 + 부분문자열이 쓰레기를 통과시키지 않는다"


def test_every_target_reaches_at_least_one_article(corpus: Corpus):
    """대상이 코퍼스에 없으면 넓혀도 0편이다 — 조용히 아무 일도 하지 않는 항목."""
    dead = {}
    for key, targets in QUERY_FORMS.items():
        reach: set[str] = set()
        for target in targets:
            for variant in expand(target):
                reach |= _doc_ids_containing(corpus, variant)
        if not reach:
            dead[key] = targets
    assert not dead, f"대상이 0편인 항목: {dead}"


# --- 동작 ---

def test_concatenated_query_now_finds_articles(corpus: Corpus):
    """핵심 동작: 붙여 쓴 질의가 0편에서 벗어난다."""
    for key in ("검색증강생성", "감사로그", "최소권한"):
        results = corpus.search(key, limit=10)
        assert results, f"{key!r} 검색이 여전히 0편이다"


def test_disabling_query_forms_returns_nothing(corpus: Corpus, monkeypatch):
    """절제 실험: 표를 끄면 이 질의들이 **0편으로 돌아가야** 한다.

    돌아가지 않는다면 결과가 다른 경로에서 온 것이고, 위 동작 테스트는
    이 기능을 전혀 검사하지 않고 있는 것이다.
    """
    import aiarchitect_blog_mcp.synonyms as syn

    for key in ("검색증강생성", "감사로그", "최소권한"):
        assert corpus.search(key, limit=10)

    monkeypatch.setattr(syn, "QUERY_FORMS", {})
    plain = Corpus()
    for key in ("검색증강생성", "감사로그", "최소권한"):
        assert not plain.search(key, limit=10), (
            f"표를 껐는데도 {key!r}가 결과를 낸다 — 동작 테스트가 질의 전용 표를 검사하지 않는다"
        )


def test_key_itself_is_not_counted():
    """키는 코퍼스에 없는 것이 수록 조건이다 — 세어 봐야 늘 0이라 넓힘에 넣지 않는다."""
    for key in QUERY_FORMS:
        assert key not in expand(key), f"{key!r}가 자기 자신으로 넓혀진다(헛일)"


def test_expansion_composes_with_synonym_groups():
    """질의형 → 코퍼스의 말 → 그 말의 동의어 묶음, 두 단계가 이어져야 한다."""
    assert set(expand("권한위임")) == {"delegation", "위임"}
    assert expand("검색증강생성") == ("rag",)   # rag는 묶음에 없다 → 그대로


def test_single_token_target_gives_identical_results(corpus: Corpus):
    """대상이 한 토큰이면, 붙여 써서 물으나 그 말로 물으나 결과·순위가 같아야 한다."""
    for key, target in (("검색증강생성", "rag"), ("대규모언어모델", "llm"), ("음성인식", "stt")):
        left = [r["id"] for r in corpus.search(key, limit=10)]
        right = [r["id"] for r in corpus.search(target, limit=10)]
        assert left == right, f"{key!r} vs {target!r}: 결과가 다르다\n{left}\n{right}"


def test_multi_word_target_matches_the_phrase_not_its_words(corpus: Corpus):
    """대상이 구(句)면 **구 전체**가 있는 글만 나온다 — 낱말이 흩어져 있는 글은 아니다.

    띄어 써서 물으면(`감사 로그`) 질의가 두 토큰으로 쪼개져 `감사`와 `로그`를 따로 센다.
    붙여 써서 물으면(`감사로그`) 구를 통째로 찾는다 — **더 정확하다.**
    """
    for key in ("감사로그", "최소권한", "도구호출"):
        phrase = expand(key)[0]
        for result in corpus.search(key, limit=10):
            record = corpus._by_id[result["id"]]
            haystack = (
                f"{record['title']} {' '.join(record['tags'])} {record['description']} "
                f"{corpus._body(record)}"
            ).lower()
            assert _term_count(haystack, phrase) > 0, (
                f"{key!r} → {result['id']}: 구 {phrase!r}가 없는데 결과에 들어왔다"
            )


def test_spaced_query_is_a_different_question(corpus: Corpus):
    """⚠️ 알려진 한계 — 띄어 써서 물으면 구가 아니라 낱말 둘이 된다(고치지 못한다).

    이 차이를 테스트로 박아 둔다. 언젠가 구 매칭이 생기면 여기서 먼저 깨지고,
    "같아야 하는 것 아니냐"는 질문에 코드가 답한다.
    """
    phrase_query = [r["id"] for r in corpus.search("감사로그", limit=10)]
    spaced_query = [r["id"] for r in corpus.search("감사 로그", limit=10)]
    assert phrase_query != spaced_query, (
        "띄어 쓴 질의가 구 질의와 같아졌다 — 구 매칭이 생겼다면 이 한계 문서를 갱신하라"
    )
    loose = [i for i in spaced_query if i not in phrase_query]
    assert loose, "띄어 쓴 질의가 구를 담지 않은 글을 올리지 않는다 — 전제가 바뀌었다"


def test_unrelated_queries_are_untouched(corpus: Corpus, monkeypatch):
    """표에 없는 질의는 영향을 받지 않아야 한다(확장이 새는지 확인)."""
    import aiarchitect_blog_mcp.synonyms as syn

    before = [r["id"] for r in corpus.search("MCP OAuth", limit=10)]
    monkeypatch.setattr(syn, "QUERY_FORMS", {})
    assert [r["id"] for r in Corpus().search("MCP OAuth", limit=10)] == before


# --- 리포트 스크립트 ---

_SPEC = importlib.util.spec_from_file_location(
    "synonym_report", Path(__file__).parents[1] / "scripts" / "synonym_report.py"
)
assert _SPEC is not None and _SPEC.loader is not None
report_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(report_mod)


def test_report_covers_query_forms(corpus: Corpus, capsys):
    assert report_mod.report_query_forms(corpus, QUERY_FORMS) == 0
    out = capsys.readouterr().out
    assert "검색증강생성" in out and "질의 전용" in out


def test_report_flags_an_underivable_key(corpus: Corpus, capsys):
    assert report_mod.report_query_forms(corpus, {"관측셩": ("관측성",)}) == 1
    assert "관측셩" in capsys.readouterr().out


def test_report_flags_a_key_that_exists_in_the_corpus(corpus: Corpus, capsys):
    """`화자분리`는 글이 실제로 쓰는 표기다 — 질의 전용 표에 있으면 안 된다."""
    assert report_mod.report_query_forms(corpus, {"화자분리": ("diarization",)}) == 1
    assert "화자분리" in capsys.readouterr().out


def test_report_flags_a_dead_target(corpus: Corpus, capsys):
    assert report_mod.report_query_forms(corpus, {"검색증강생성": ("존재하지않는말",)}) == 1
    assert "검색증강생성" in capsys.readouterr().out


def test_term_matching_is_unchanged():
    assert _term_count("블로그를 운영한다", "로그") == 0
    assert _term_count("감사 로그를 남긴다", "감사 로그") == 1
