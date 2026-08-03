"""코퍼스 파서·검색 골든 테스트.

빌드된 인덱스(data/articles_index.json)가 있어야 통과한다:
    python scripts/build_index.py
"""

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


# --- 코퍼스(빌드 산출물) 골든 테스트 ---

def test_corpus_count_is_49():
    assert len(Corpus().records) == 49


def test_seven_categories_sum_to_49():
    cats = Corpus().categories()
    assert len(cats) == 7
    assert sum(c["count"] for c in cats) == 49


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


def test_bundled_articles_have_no_editorial_frontmatter():
    """번들 원본 49편에 내부 편집 헤더(상태·Boss 승인·권장*·내부 경로)가 없어야 한다."""
    markers = [
        "# Tistory 기술자료 초안", "검토용 초안", "공개 게시 전 Boss", "Boss 게시 승인",
        "권장 제목", "권장 태그", "권장 대표 이미지", "portfolio/architecture-diagrams",
        "도식 정책", "공개 URL: `미발급`",
    ]
    files = sorted((DATA_DIR / "articles").glob("*.md"))
    assert len(files) == 49
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("# "), f"{f.name}: 실제 H1로 시작하지 않음"
        for m in markers:
            assert m not in text, f"{f.name}: 내부 편집 마커 노출 → {m!r}"


def test_no_internal_repo_paths_in_bundled_data():
    """번들 인덱스·본문에 내부 저장소 경로 식별자가 없어야 한다(공개 배포 안전)."""
    import json
    forbidden = ["github-portfolio-public", "aiarchitect/blogs"]
    idx = json.loads((DATA_DIR / "articles_index.json").read_text(encoding="utf-8"))
    for f in forbidden:
        assert f not in json.dumps(idx, ensure_ascii=False), f"인덱스에 내부 경로: {f}"
    for p in sorted((DATA_DIR / "articles").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        for f in forbidden:
            assert f not in text, f"{p.name}: 내부 경로 노출 → {f}"


def test_rendered_articles_have_no_internal_markers():
    """서빙(render_article) 결과에도 내부 편집 마커가 없어야 한다."""
    c = Corpus()
    for r in c.records:
        md = c.render_article(r["id"])
        for m in ("Boss", "검토용 초안", "portfolio/architecture-diagrams", "권장 대표 이미지"):
            assert m not in md, f"{r['id']}: 렌더 결과에 내부 마커 → {m!r}"


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


def test_get_article_includes_backlink_twice():
    md = Corpus().render_article("09")
    assert md.count("aiarchitect.tistory.com") >= 2  # 상단 + 하단 백링크
    assert md.startswith("# ")


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
