"""게시용 비계(scaffolding) 제거 테스트.

소스 글은 티스토리에 그대로 붙여 넣을 수 있게 목차 장치를 품고 있다. 번들은 에이전트가
읽는 것이므로 빌드에서 걷어낸다. 걷어낸 상태는 **아무도 보지 않으면 조용히 되돌아온다** —
옛 스크립트로 재빌드하거나, 새 글이 다른 양식을 쓰면 그만이다. 여기서 번들 자체를 검사한다.

🔴 가장 중요한 것은 `test_code_blocks_are_never_touched`다. 코드 블록 안에는 Maven POM
(`<version>`·`<artifactId>`)과 XML 예제가 있어, 태그로 보고 지우면 **예제가 조용히 깨진다**.
"""

from __future__ import annotations

import re

import pytest

from aiarchitect_blog_mcp.corpus import (
    Corpus,
    strip_publishing_scaffolding,
)

# 번들에 남아 있으면 안 되는 것들 — 전부 게시용 장치다.
SCAFFOLDING_MARKERS = (
    "aiarchitect-toc",     # 목차를 감싼 요소의 id
    "ai-section-",         # 목차가 가리키는 앵커
    "data-ke-",            # 티스토리 에디터 속성(-style·-size 등 형제가 여럿이다)
    "box-sizing",          # 인라인 CSS
    "text-underline-offset",
    "scroll-margin-top",
)

_FENCE = re.compile(r"^```.*?^```", re.S | re.M)


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus()


# --- 번들 상태 ---

def test_bundle_has_no_publishing_scaffolding(corpus: Corpus):
    """번들 어디에도 목차 장치가 남아 있으면 안 된다."""
    found: dict[str, list[str]] = {}
    for record in corpus.records:
        body = corpus._body(record).lower()
        hits = [m for m in SCAFFOLDING_MARKERS if m in body]
        if hits:
            found[record["id"]] = hits
    assert not found, (
        f"번들에 게시용 장치가 남아 있다: {found} — 옛 스크립트로 빌드했거나 "
        f"새 글이 다른 양식을 쓴다. `uv run python scripts/build_index.py <정본경로>` 재실행"
    )


def test_bundle_has_no_inline_style_attributes(corpus: Corpus):
    """인라인 `style=`는 검색어로 세어지고 `get_article` 응답에도 그대로 나간다.

    코드 블록 안은 제외한다 — 거기 있는 `style=`는 글이 설명하는 예제다.
    """
    styled = [
        r["id"] for r in corpus.records
        if re.search(r"<[a-z][^>]*\sstyle=", _FENCE.sub("", corpus._body(r)), re.I)
    ]
    assert not styled, f"인라인 style 속성이 남은 글: {styled}"


def test_source_really_had_scaffolding_so_the_guard_is_not_vacuous():
    """절제: 위 가드가 **무언가를 실제로 막고 있는지** 확인한다.

    번들이 깨끗한 것이 "원래 깨끗해서"라면 가드는 아무 일도 하지 않는 셈이다.
    제거 함수에 소스 모양을 넣어 보고, 넣기 전에는 걸리는지 본다.
    """
    source = (
        "# 제목\n\n"
        '<blockquote id="aiarchitect-toc" data-ke-style="box" style="box-sizing: border-box;">\n'
        '<ol><li><a href="#ai-section-1" style="color: #0070d1;">첫 절</a></li></ol>\n'
        "</blockquote>\n\n"
        "본문입니다.\n"
    )
    assert any(m in source for m in SCAFFOLDING_MARKERS), "시험 입력에 장치가 없다"
    cleaned = strip_publishing_scaffolding(source)
    assert not any(m in cleaned for m in SCAFFOLDING_MARKERS), "제거가 동작하지 않는다"
    assert "본문입니다." in cleaned


# --- 무엇을 지우고 무엇을 남기는가 ---

def test_code_blocks_are_never_touched():
    """🔴 코드 블록 안은 **글자 하나도** 바뀌면 안 된다.

    Maven POM의 `<version>`, XML 예제의 `<CustomerRow>`, HTML 설명의 `<h2>`가 펜스 안에 있다.
    태그로 보고 지우면 예제가 깨지는데, 깨진 예제는 테스트가 없으면 아무도 모른다.
    """
    fenced = (
        "# 제목\n\n"
        "```xml\n"
        "<project>\n"
        "  <dependency><artifactId>spring-core</artifactId><version>6.1.0</version></dependency>\n"
        "</project>\n"
        "```\n\n"
        "```html\n"
        '<blockquote id="aiarchitect-toc" style="box-sizing: border-box;">목차</blockquote>\n'
        '<h2 id="ai-section-1">제목 예시</h2>\n'
        "```\n\n"
        "본문입니다.\n"
    )
    cleaned = strip_publishing_scaffolding(fenced)
    for line in ("<artifactId>spring-core</artifactId>", "<version>6.1.0</version>",
                 '<blockquote id="aiarchitect-toc" style="box-sizing: border-box;">목차</blockquote>',
                 '<h2 id="ai-section-1">제목 예시</h2>'):
        assert line in cleaned, f"코드 블록 안이 바뀌었다 — 사라진 줄: {line}"


def test_html_headings_become_markdown_headings():
    """양식 A — 제목이 HTML 안에 있다. **제목은 내용이므로** 지우지 말고 되돌린다."""
    source = (
        "# 제목\n\n"
        '<h2 id="ai-section-1" style="scroll-margin-top: 96px;">1. 목적을 정의한다</h2>\n\n'
        "본문.\n\n"
        '<h3 id="ai-section-2" style="scroll-margin-top: 96px;">세부 항목</h3>\n'
    )
    cleaned = strip_publishing_scaffolding(source)
    assert "## 1. 목적을 정의한다" in cleaned
    assert "### 세부 항목" in cleaned
    assert "<h2" not in cleaned and "scroll-margin-top" not in cleaned


def test_empty_anchors_go_but_anchors_with_content_stay():
    """양식 B — 빈 앵커는 내용이 없어 지운다. 글이 **설명 중인** `<a>`는 남겨야 한다."""
    source = (
        "# 제목\n\n"
        '<a id="ai-section-1"></a>\n\n'
        "## 1. 첫 절\n\n"
        '숨겨도 `<a href="/archive/202609">`는 HTML에 그대로 남습니다.\n'
    )
    cleaned = strip_publishing_scaffolding(source)
    assert '<a id="ai-section-1"></a>' not in cleaned
    assert "## 1. 첫 절" in cleaned
    assert '<a href="/archive/202609">' in cleaned, "본문이 설명하는 HTML 예시가 지워졌다"


def test_toc_is_removed_whatever_element_wraps_it():
    """⚠️ 목차를 감싼 요소는 글마다 다르다 — 대부분 blockquote지만 div인 글도 있다(63번).

    태그 이름을 고정했다가 그 글 하나가 조용히 빠져나갔었다.
    """
    for tag in ("blockquote", "div"):
        source = (
            f'# 제목\n\n<{tag} id="aiarchitect-toc" style="box-sizing: border-box;">\n'
            f'<ol><li><a href="#ai-section-1">첫 절</a></li></ol>\n</{tag}>\n\n본문.\n'
        )
        cleaned = strip_publishing_scaffolding(source)
        assert "aiarchitect-toc" not in cleaned, f"<{tag}> 목차가 남았다"
        assert "본문." in cleaned


def test_markdown_autolinks_and_generics_survive():
    """태그처럼 보이지만 내용인 것들 — 지우면 본문이 훼손된다."""
    source = (
        "# 제목\n\n"
        "원문은 <https://aiarchitect.tistory.com/9> 입니다.\n\n"
        "`Map<String, String>`과 `List<T>`를 씁니다. 값은 <TOKEN>으로 둡니다.\n\n"
        "![그림](assets/blog-92-state.png)\n"
    )
    cleaned = strip_publishing_scaffolding(source)
    for keep in ("<https://aiarchitect.tistory.com/9>", "Map<String, String>", "List<T>", "<TOKEN>"):
        assert keep in cleaned, f"내용이 지워졌다: {keep}"


def test_stripping_is_idempotent(corpus: Corpus):
    """번들은 이미 걷어낸 상태다 — 다시 적용해도 그대로여야 재빌드가 안정적이다."""
    for record in corpus.records:
        body = corpus._body(record)
        assert strip_publishing_scaffolding(body) == body, (
            f"{record['id']}: 번들 본문에 제거가 한 번 더 먹는다 — 빌드가 멱등하지 않다"
        )


# --- 효과 ---

def test_css_tokens_are_no_longer_searchable(corpus: Corpus):
    """검색이 CSS를 세지 않는다 — 이것이 이 작업의 요점이다."""
    for junk in ("box-sizing", "f6f9fc", "data-ke-style"):
        assert not corpus.search(junk, limit=5), f"{junk!r}가 아직 검색된다"


def test_section_titles_are_still_searchable(corpus: Corpus):
    """🔬 목차를 지웠다고 **섹션 제목까지** 사라지면 안 된다.

    목차 항목은 본문 헤딩의 중복이었다. 중복이 아니었다면 내용을 잃은 것이다.
    """
    body = corpus._body(corpus._by_id["27"])
    assert "감사 로그의 목적을 먼저 정의한다" in body, "섹션 제목이 사라졌다 — 목차가 중복이 아니었다"
    assert body.count("감사 로그의 목적을 먼저 정의한다") == 1, "제목이 아직 두 번 세어진다"


def test_markdown_toc_blockquote_is_removed_but_handwritten_one_is_kept():
    """세 번째 양식 — 순수 마크다운 목차(5편). 생성된 앵커를 담은 것만 지운다."""
    generated = (
        "# 제목\n\n> **목차**\n>\n> 1. [첫 절](#ai-section-1)\n> 2. [둘째 절](#ai-section-2)\n\n본문.\n"
    )
    cleaned = strip_publishing_scaffolding(generated)
    assert "ai-section" not in cleaned and "본문." in cleaned

    handwritten = "# 제목\n\n> **목차**\n>\n> 1. 손으로 적은 항목\n\n본문.\n"
    assert strip_publishing_scaffolding(handwritten) == handwritten.strip(), (
        "생성된 앵커가 없는 인용블록까지 지웠다 — 사람이 쓴 목차를 잃는다"
    )


def test_section_cross_references_keep_their_text():
    """본문 안 `[11절](#ai-section-11)`은 앵커가 사라져 깨진 링크가 된다 — 글자는 남긴다."""
    source = "# 제목\n\n`(Key, Code)` 목록은 [11절](#ai-section-11)의 Golden Vector를 씁니다.\n"
    cleaned = strip_publishing_scaffolding(source)
    assert "11절의 Golden Vector" in cleaned
    assert "#ai-section-11" not in cleaned
    assert "[11절]" not in cleaned
