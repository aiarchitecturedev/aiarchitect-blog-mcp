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
    DATA_DIR,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    Corpus,
    _clamp_int,
    build_record,
    extract_body,
    is_published,
    parse_metadata,
)

EXPECTED_IDS = [f"{number:02d}" for number in range(1, 70)]
EXPECTED_CATEGORY_COUNTS = {
    "보안": 19,
    "엔터프라이즈 아키텍처": 14,
    "개발 도구 · 자동화": 11,
    "AI Agent · MCP": 8,
    "기술 인사이트": 6,
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


# --- 코퍼스(69편 빌드 산출물) 골든 테스트 ---


def test_index_corpus_and_bundle_have_the_same_expected_69_articles():
    index = json.loads((DATA_DIR / "articles_index.json").read_text(encoding="utf-8"))
    index_records = index["articles"]
    corpus = Corpus()
    bundle_files = sorted((DATA_DIR / "articles").glob("*.md"))

    assert index["count"] == 69
    assert len(index_records) == 69
    assert [record["id"] for record in index_records] == EXPECTED_IDS
    assert [record["id"] for record in corpus.records] == EXPECTED_IDS
    assert [record["file"] for record in index_records] == [path.name for path in bundle_files]
    assert len(bundle_files) == 69


def test_seven_categories_match_target_counts():
    actual = Counter(record["category"] for record in Corpus().records)
    assert actual == Counter(EXPECTED_CATEGORY_COUNTS)
    assert sum(actual.values()) == 69


def test_ids_and_official_urls_are_unique_and_complete():
    corpus = Corpus()
    ids = [record["id"] for record in corpus.records]
    urls = [record["url"] for record in corpus.records]

    assert ids == EXPECTED_IDS
    assert len(ids) == len(set(ids)) == 69
    assert len(urls) == len(set(urls)) == 69
    assert all(is_published(url) for url in urls)
    assert corpus.excluded_ids == []


def test_default_pagination_combines_50_and_19_into_69():
    corpus = Corpus()
    first_page = corpus.list_articles()
    second_page = corpus.list_articles(offset=50)
    combined_ids = [record["id"] for record in first_page + second_page]

    assert len(first_page) == 50
    assert len(second_page) == 19
    assert combined_ids == EXPECTED_IDS
    assert len(set(combined_ids)) == 69


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
    assert len(files) == 69
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


def test_search_finds_relevant_article():
    res = Corpus().search("MCP OAuth PKCE", limit=5)
    assert res, "검색 결과가 비어 있음"
    assert all("url" in r and "snippet" in r for r in res)


def test_search_body_and_backlinks_for_new_corpus_articles():
    corpus = Corpus()
    queries = {
        "50": "Log Forging",
        "61": "출처 링크",
        "69": "익명성 게이트",
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
