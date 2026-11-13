"""코퍼스 파서·검색 골든 테스트.

빌드된 인덱스(data/articles_index.json)가 있어야 통과한다:
    python scripts/build_index.py
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from aiarchitect_blog_mcp.corpus import (
    BLOG_HOME,
    _BM25_K1,
    _bm25_tf,
    DATA_DIR,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    Corpus,
    _clamp_int,
    _idf,
    _term_count,
    build_record,
    extract_body,
    is_published,
    parse_metadata,
)

# 서빙되는 글 번호(= 티스토리 글 번호). 36·37·97·98은 원본에 글이 없고,
# 89·90은 정식 게시 URL이 없어 fail-closed로 제외된다.
# build_index와 독립적으로 기대값을 다시 적는다(골든 테스트).
EXPECTED_IDS = [
    f"{n:02d}"
    for n in [*range(1, 36), *range(38, 89), *range(91, 97), 99, 100]
]
EXPECTED_COUNT = 94
EXPECTED_CATEGORY_COUNTS = {
    "엔터프라이즈 아키텍처": 28,
    "보안": 19,
    "AI Agent · MCP": 14,
    "개발 도구 · 자동화": 11,
    "기술 인사이트": 11,
    "프로젝트 문제 해결": 6,
    "RAG · LLM 시스템": 5,
}
def _load_private_tokens() -> tuple[str, ...]:
    """비배포 로컬 denylist(.private-tokens)에서 토큰을 로드한다.

    개인 식별자 리터럴을 tracked 소스에 남기지 않기 위해 외부 파일에서 읽는다(release #16).
    파일이 없으면 빈 튜플(관련 테스트는 skip).
    """
    path = Path(__file__).parents[1] / ".private-tokens"
    if not path.exists():
        return ()
    return tuple(
        s.lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if (s := line.strip()) and not s.startswith("#")
    )


FORBIDDEN_PRIVATE_TOKENS = _load_private_tokens()


# --- 순수 파서 테스트(데이터 불필요) ---

def test_extract_body_strips_header():
    text = "# 제목\n\n- 문서 ID: `BLOG-01`\n- 상태: 공개 완료\n\n## 개요\n본문 시작\n"
    body = extract_body(text)
    assert body.startswith("## 개요")
    assert "문서 ID" not in body


def test_extract_body_drops_unknown_internal_header_keys():
    """화이트리스트에 없는 내부 편집 bullet도 공개 본문에 남으면 안 된다.

    소스 헤더 키는 글마다 제각각이라(⚠️ 유출 주의·🔴 발행 전 확인·내부 링크 대상 …)
    헤더의 끝을 키 목록으로 정할 수 없다. 보일러플레이트 H1 다음의 실제 H1부터가 본문이다.
    """
    text = (
        "# Tistory 기술자료 초안\n\n"
        "- 문서 ID: `BLOG-77`\n"
        "- 분류: `AI Agent · MCP`\n"
        "- ⚠️ 유출 주의: 내부 고객사명 언급 금지\n"
        "- 🔴 발행 전 확인: 도식 2장 재렌더\n"
        "- 내부 링크 대상: `/admin/draft/77`\n\n"
        "---\n\n"
        "# 실제 공개 제목\n\n"
        "본문 시작\n"
    )
    body = extract_body(text)
    assert body.startswith("# 실제 공개 제목")
    for leaked in ("유출 주의", "발행 전 확인", "내부 링크 대상", "/admin/draft/77", "기술자료 초안"):
        assert leaked not in body, leaked


def test_extract_body_leaves_already_cleaned_bundle_body_untouched():
    """번들된 본문은 이미 실제 H1로 시작한다 — 서빙 경로에서 다시 잘리면 안 된다."""
    text = "# 실제 공개 제목\n\n본문 첫 줄\n\n- 절 제목 끝 라벨: 본문에 있는 평범한 불릿\n\n## 1절\n"
    assert extract_body(text) == text.strip()


def test_published_title_key_wins_over_filename_fallback():
    """BLOG-76~90은 `권장 제목`이 아니라 `게시 제목`을 쓴다(파일명이 제목이 되면 안 된다)."""
    text = (
        "# Tistory 기술자료 초안\n"
        "- 문서 ID: `BLOG-77`\n"
        "- 분류: `AI Agent · MCP`\n"
        "- 게시 제목: `AI Agent 실행 계약 설계`\n\n"
        "# AI Agent 실행 계약 설계\n\n본문"
    )
    rec = build_record_from_text(text, "77-ai-agent-orchestration-mcp-a2a.md")
    assert rec["title"] == "AI Agent 실행 계약 설계"


def test_three_digit_article_id_is_parsed_and_served():
    text = (
        "# Tistory 기술자료 초안\n"
        "- 문서 ID: `BLOG-100`\n"
        "- 분류: `기술 인사이트`\n"
        "- 게시 제목: `세 자리 글`\n"
        "- 공개 URL: `https://aiarchitect.tistory.com/100`\n\n"
        "# 세 자리 글\n\n본문"
    )
    rec = build_record_from_text(text, "100-tistory-ua-split-crawler-view.md")
    assert rec["id"] == "100"
    assert rec["published"] is True


def test_article_id_equals_tistory_post_number():
    """id는 원문 글 번호와 같다 — 에이전트가 인용한 출처 URL과 id가 어긋나지 않도록."""
    for record in Corpus().records:
        assert record["id"].lstrip("0") == record["url"].rstrip("/").rsplit("/", 1)[-1], record


def test_parse_metadata_variants():
    # 확장 포맷: 권장 제목 / 권장 태그
    text1 = "# t\n- 문서 ID: `BLOG-09`\n- 분류: `보안`\n- 권장 제목: `제목A`\n- 권장 태그: `MCP`, `OAuth`\n\n본문"
    r1 = build_record_from_text(text1, "09-x.md")
    assert r1["doc_id"] == "BLOG-09"
    assert r1["title"] == "제목A"
    assert r1["tags"] == ["MCP", "OAuth"]

    # 구 포맷: 제목 / 태그, 문서 ID 없음 → 파일명 폴백
    text2 = "# t\n- 상태: 공개 완료\n- 분류: `기술 인사이트`\n- 제목: `제목B`\n- 태그: `RAG`, `LLM`\n\n본문"
    r2 = build_record_from_text(text2, "14-y.md")
    assert r2["id"] == "14"
    assert r2["title"] == "제목B"
    assert r2["tags"] == ["RAG", "LLM"]


def test_unpublished_url_falls_back_home():
    text = "# t\n- 문서 ID: `BLOG-45`\n- 분류: `엔터프라이즈 아키텍처`\n- 권장 제목: `x`\n- 공개 URL: `미발급`\n\n본문"
    rec = build_record_from_text(text, "45-z.md")
    assert rec["url"] == BLOG_HOME
    assert rec["published"] is False  # fail-closed: 홈 폴백은 미게시로 표시


def test_published_url_marks_published():
    text = "# t\n- 문서 ID: `BLOG-09`\n- 분류: `보안`\n- 권장 제목: `x`\n- 공개 URL: `https://aiarchitect.tistory.com/11`\n\n본문"
    rec = build_record_from_text(text, "09-x.md")
    assert rec["url"] == "https://aiarchitect.tistory.com/11"
    assert rec["published"] is True


def test_is_published_rules():
    assert is_published("https://aiarchitect.tistory.com/2")
    assert is_published("https://aiarchitect.tistory.com/52/")
    assert not is_published("https://aiarchitect.tistory.com")   # 홈
    assert not is_published("https://aiarchitect.tistory.com/")  # 홈(슬래시)
    assert not is_published("")
    assert not is_published("https://evil.example.com/2")        # 다른 호스트


def test_is_published_rejects_zero_and_non_str():
    assert not is_published("https://aiarchitect.tistory.com/0")   # 0 거부
    assert not is_published("https://aiarchitect.tistory.com/00")  # 앞자리 0 거부
    assert not is_published(None)                                  # 비문자열
    assert not is_published(123)                                   # 비문자열


def test_is_published_rejects_unicode_digits():
    """Tistory 글 번호는 ASCII 정수만. 전각·아랍·위첨자 숫자 우회를 차단한다."""
    assert not is_published("https://aiarchitect.tistory.com/1２")  # 전각 2
    assert not is_published("https://aiarchitect.tistory.com/1٢")  # 아랍-인도 2
    assert not is_published("https://aiarchitect.tistory.com/²")   # 위첨자 2
    assert is_published("https://aiarchitect.tistory.com/12")      # 정상 ASCII


def test_clamp_int_handles_infinity_and_bool():
    assert _clamp_int(float("inf"), 10, 0, 200) == 10   # OverflowError → default
    assert _clamp_int(float("-inf"), 10, 0, 200) == 10
    assert _clamp_int(float("nan"), 10, 0, 200) == 10   # int(nan) → ValueError
    assert _clamp_int(True, 10, 0, 200) == 10           # bool 거부 → default
    assert _clamp_int(5, 10, 0, 200) == 5               # 정상
    assert _clamp_int(999, 10, 0, 200) == 200           # 상한 클램프


def test_is_published_rec_strict_fail_closed():
    """published 플래그를 이용한 우회(홈 URL·외부 도메인·문자열 참값)를 모두 차단한다."""
    rec_is = Corpus._is_published_rec
    assert not rec_is({"url": "https://aiarchitect.tistory.com/", "published": True})   # 홈+참
    assert not rec_is({"url": "https://evil.example.com/2", "published": True})         # 외부+참
    assert not rec_is({"url": "https://aiarchitect.tistory.com/2", "published": "false"})  # "false"
    assert rec_is({"url": "https://aiarchitect.tistory.com/2", "published": True})      # 정식+참
    assert rec_is({"url": "https://aiarchitect.tistory.com/2"})                         # 플래그 없음→URL
    assert not rec_is({"url": "https://aiarchitect.tistory.com/"})                      # 홈, 플래그 없음


# --- 코퍼스(94편 빌드 산출물) 골든 테스트 ---


def test_index_corpus_and_bundle_have_the_same_expected_94_articles():
    index = json.loads((DATA_DIR / "articles_index.json").read_text(encoding="utf-8"))
    index_records = index["articles"]
    corpus = Corpus()
    bundle_files = sorted((DATA_DIR / "articles").glob("*.md"))

    assert index["count"] == EXPECTED_COUNT
    assert len(index_records) == EXPECTED_COUNT
    assert [record["id"] for record in index_records] == EXPECTED_IDS
    assert [record["id"] for record in corpus.records] == EXPECTED_IDS
    # 인덱스는 글 번호 숫자순, 디스크 glob은 사전순("100" < "11")이라 집합으로 비교한다.
    assert {record["file"] for record in index_records} == {path.name for path in bundle_files}
    assert len(bundle_files) == EXPECTED_COUNT


def test_seven_categories_match_target_counts():
    actual = Counter(record["category"] for record in Corpus().records)
    assert actual == Counter(EXPECTED_CATEGORY_COUNTS)
    assert sum(actual.values()) == EXPECTED_COUNT


def test_ids_and_official_urls_are_unique_and_complete():
    corpus = Corpus()
    ids = [record["id"] for record in corpus.records]
    urls = [record["url"] for record in corpus.records]

    assert ids == EXPECTED_IDS
    assert len(ids) == len(set(ids)) == EXPECTED_COUNT
    assert len(urls) == len(set(urls)) == EXPECTED_COUNT
    assert all(is_published(url) for url in urls)
    assert corpus.excluded_ids == []


def test_default_pagination_combines_50_and_44_into_94():
    corpus = Corpus()
    first_page = corpus.list_articles()
    second_page = corpus.list_articles(offset=50)
    combined_ids = [record["id"] for record in first_page + second_page]

    assert len(first_page) == 50
    assert len(second_page) == 44
    assert combined_ids == EXPECTED_IDS
    assert len(set(combined_ids)) == EXPECTED_COUNT


def test_every_record_has_title_category_url():
    for r in Corpus().records:
        assert r["title"], r
        assert r["category"], r
        assert r["url"].startswith("http"), r


def test_fail_closed_no_home_fallback_served():
    """서빙되는 모든 글은 정식 게시 URL을 가진다(홈 폴백 미노출)."""
    c = Corpus()
    for r in c.records:
        assert is_published(r["url"]), f"홈 폴백이 노출됨: {r['id']} -> {r['url']}"
    assert c.excluded_ids == [], f"제외 대상이 남아 있음: {c.excluded_ids}"


def test_bundled_articles_start_with_h1_and_have_no_editorial_metadata():
    """번들 원본은 실제 H1로 시작하고 파서가 읽을 편집 메타데이터가 없어야 한다."""
    files = sorted((DATA_DIR / "articles").glob("*.md"))
    assert len(files) == EXPECTED_COUNT
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("# "), f"{f.name}: 실제 H1로 시작하지 않음"
        assert parse_metadata(text) == {}, f"{f.name}: 편집 메타데이터가 남아 있음"


def test_no_exact_private_identifiers_in_bundled_data():
    """정확한 비공개 토큰을 차단하되 일반적인 `/Users/` 예시는 허용한다."""
    if not FORBIDDEN_PRIVATE_TOKENS:
        pytest.skip(".private-tokens 미존재 — 정확 토큰 검사 생략(유지관리자 로컬 정책 파일 필요)")
    idx = json.loads((DATA_DIR / "articles_index.json").read_text(encoding="utf-8"))
    index_text = json.dumps(idx, ensure_ascii=False).lower()
    for token in FORBIDDEN_PRIVATE_TOKENS:
        assert token not in index_text, f"인덱스에 비공개 식별자: {token}"
    for p in sorted((DATA_DIR / "articles").glob("*.md")):
        text = p.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_PRIVATE_TOKENS:
            assert token not in text, f"{p.name}: 비공개 식별자 노출 → {token}"


def test_private_tokens_not_reintroduced_as_literals_in_tracked_sources():
    """externalized denylist가 tracked 소스에 리터럴로 재유입되지 않았는지 회귀 검증.

    개인 식별자는 오직 비추적 `.private-tokens`에만 존재해야 한다.
    """
    if not FORBIDDEN_PRIVATE_TOKENS:
        pytest.skip(".private-tokens 미존재")
    root = Path(__file__).parents[1]
    targets = [
        root / "scripts" / "build_index.py",
        root / "tests" / "test_corpus.py",
        root / "tests" / "test_build_index.py",
        root / "pyproject.toml",
        root / "README.md",
    ]
    for f in targets:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_PRIVATE_TOKENS:
            assert token not in text, f"{f.name}: denylist 토큰 리터럴 재유입 → {token}"


def test_list_articles_clamps_negative_and_oversized():
    c = Corpus()
    assert c.list_articles(limit=-5) == []          # 음수 → 0으로 클램프
    assert c.list_articles(offset=-10, limit=1) == c.list_articles(offset=0, limit=1)
    assert len(c.list_articles(limit=10_000)) <= MAX_LIST_LIMIT
    assert c.list_articles(limit="oops") != []      # 잘못된 타입 → 기본값


def test_search_clamps_limit_and_bad_query():
    c = Corpus()
    assert len(c.search("MCP", limit=9999)) <= MAX_SEARCH_LIMIT
    assert c.search("MCP", limit=-1) == []
    assert c.search("") == []
    assert c.search("   ") == []


def test_term_matching_requires_a_leading_boundary():
    """한국어는 교착어라 뒤는 열고 앞은 막는다 — "로그를"은 맞고 "블로그"는 아니다."""
    assert _term_count("로그를 남긴다", "로그") == 1      # 조사
    assert _term_count("평가합니다", "평가") == 1          # 어미
    assert _term_count("블로그를 운영한다", "로그") == 0    # 내부 일치
    assert _term_count("카탈로그", "로그") == 0
    assert _term_count("ai agent", "ai") == 1
    assert _term_count("chain", "ai") == 0                # 영어 내부 일치
    assert _term_count("mcp를 붙인다", "mcp") == 1


def test_search_does_not_match_blog_when_looking_for_logs():
    """회귀: 블로그 저장소라 '블로그'가 어디에나 있어 '로그' 검색을 오염시켰다."""
    corpus = Corpus()
    for result in corpus.search("로그", limit=5):
        record = corpus._by_id[result["id"]]
        haystack = (
            record["title"] + " " + " ".join(record["tags"]) + " "
            + record["description"] + " " + corpus._body(record)
        ).lower()
        assert _term_count(haystack, "로그") > 0, f"{result['id']}: 경계 밖 일치로 올라옴"


def test_idf_weights_rare_terms_higher():
    """희귀어가 흔한 단어보다 무거워야 한다. 거의 모든 글에 있는 단어는 글을 구분하지 못한다."""
    total = 94
    rare, common, everywhere = _idf(total, 1), _idf(total, 50), _idf(total, total)
    assert rare > common > everywhere
    assert everywhere < 0.05, f"모든 글에 있는 단어의 가중치가 너무 큼: {everywhere}"
    # df가 커질수록 단조 감소해야 한다.
    values = [_idf(total, df) for df in range(1, total + 1)]
    assert values == sorted(values, reverse=True)


def test_top_results_cover_every_query_term():
    """다중어 질의의 상위 결과는 질의어를 **전부** 담고 있어야 한다.

    이전 구현에서는 "RAG 청킹" 검색에 청킹이 한 번도 없는 글이 rag 빈도만으로 3위였다.
    """
    corpus = Corpus()
    for query in ("RAG 청킹", "AI Agent 평가", "MCP 보안"):
        terms = query.lower().split()
        for result in corpus.search(query, limit=3):
            record = corpus._by_id[result["id"]]
            missing = [t for t in terms if corpus._weighted_tf(record, t) == 0]
            assert not missing, f"{query} → {result['id']}: 질의어 누락 {missing}"


def test_longer_document_scores_lower_at_equal_frequency():
    """같은 빈도라면 짧은 글이 더 높아야 한다(길이 정규화).

    긴 글은 단순히 분량 때문에 빈도가 쌓인다. 보정이 없으면 분량이 관련도로 둔갑한다.
    """
    avg = 20_000
    short = _bm25_tf(10, 5_000, avg)
    average = _bm25_tf(10, avg, avg)
    long_doc = _bm25_tf(10, 80_000, avg)
    assert short > average > long_doc


def test_bm25_tf_saturates_with_frequency():
    """빈도 항은 포화한다 — 10배 빈도가 10배 점수가 되지 않는다."""
    avg = 20_000
    once, ten, hundred = (_bm25_tf(n, avg, avg) for n in (1, 10, 100))
    assert once < ten < hundred                 # 단조 증가는 유지
    assert ten / once < 5                       # 그러나 10배는 아니다
    assert hundred < _BM25_K1 + 1               # 상한에 수렴


def test_term_frequency_saturates():
    """같은 단어가 100번 나왔다고 1번의 100배가 되면 안 된다(BM25 포화).

    점수 배율을 **같은 글들의 빈도 배율과 비교**한다. 상위 N개만 보면 꼬리가 잘려
    포화가 없어도 배율이 작아 보인다(실제로 그렇게 헛돌았다).
    """
    corpus = Corpus()
    results = corpus.search("MCP", limit=MAX_SEARCH_LIMIT)
    assert len(results) > 10

    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)

    freqs = [corpus._weighted_tf(corpus._by_id[r["id"]], "mcp") for r in results]
    freq_ratio = max(freqs) / min(freqs)
    score_ratio = scores[0] / scores[-1]
    assert freq_ratio > 10, f"포화를 검사할 만큼 빈도 차이가 없음: {freq_ratio}"
    assert score_ratio < freq_ratio / 5, (
        f"점수가 빈도에 거의 비례함(포화 없음): 빈도 {freq_ratio:.0f}배 → 점수 {score_ratio:.1f}배"
    )


def test_search_finds_relevant_article():
    res = Corpus().search("MCP OAuth PKCE", limit=5)
    assert res, "검색 결과가 비어 있음"
    assert all("url" in r and "snippet" in r for r in res)


def test_search_body_and_backlinks_for_new_corpus_articles():
    corpus = Corpus()
    queries = {
        "61": "Log Forging",
        "63": "블로그 MCP 서버",
        "68": "익명성 게이트",
        "91": "Assurance Case",   # 94편 갱신분
        "100": "User-Agent 크롤러",  # 세 자리 id 회귀
    }
    by_id = {record["id"]: record for record in corpus.records}

    for article_id, query in queries.items():
        results = corpus.search(query, limit=50)
        assert article_id in {record["id"] for record in results}, (article_id, query)

        rendered = corpus.render_article(article_id)
        article_url = by_id[article_id]["url"]
        assert rendered.startswith("# ")
        assert article_url in rendered
        assert rendered.count(article_url) >= 2  # 상단 원문 + 하단 백링크


def test_get_article_unknown_id_is_graceful():
    md = Corpus().render_article("999")
    assert "찾을 수 없습니다" in md


# --- 헬퍼 ---

def build_record_from_text(text: str, name: str) -> dict:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / name
        p.write_text(text, encoding="utf-8")
        return build_record(p)
