"""죽은 이미지 링크 → 캡션 변환 테스트.

소스 글의 이미지는 전부 상대경로 `assets/...`라 번들에서는 어느 쪽으로도 열리지 않는다.
원문의 CDN 주소를 대신 넣는 길은 막혀 있다 — **서명·만료가 붙은 링크**라서 배포본에 구워
넣으면 2주쯤 뒤 전부 죽는다(작동하는 척하다 깨지므로 지금보다 나쁘다). 그래서 링크는
버리고 alt 를 캡션으로 남긴다 — alt 는 도식을 한 문장으로 설명하는 내용이다.

🔴 가장 중요한 것은 `test_code_blocks_are_never_touched`다. 코드 블록 안의 `![...](...)`와
`<img>`는 글이 **설명하는 예제**다. 본문과 같이 처리하면 예제가 조용히 깨진다.

두 번째는 `test_find_dead_image_refs_catches_inline_form`이다. 변환은 단독 줄만 바꾸므로
문장 중간에 낀 이미지는 빠져나간다. 그 구멍을 빌드 프리플라이트가 막는다는 것이 이 테스트다.
"""

from __future__ import annotations

import re

import pytest

from aiarchitect_blog_mcp.corpus import (
    Corpus,
    find_dead_image_refs,
    strip_publishing_scaffolding,
)

_CAPTION = re.compile(r"^> 🖼️ \*\*그림\*\*: (.+)$", re.M)

# 2026-11-17 실측: 마크다운 299 + HTML 6 = 305개가 86편에 들어 있다.
# 🔴 정확한 수가 아니라 **하한**으로 둔다 — 글이 늘면 캡션도 늘기 때문이다. 이 가드가 잡으려는
# 것은 "하나 늘었다"가 아니라 **캡션이 통째로 사라지는 회귀**(옛 스크립트로 재빌드 등)다.
MIN_CAPTIONS = 300
MIN_ARTICLES_WITH_CAPTION = 80


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus()


# --- 번들 상태 ---

def test_bundle_has_no_dead_image_links(corpus: Corpus):
    """번들 어디에도 열리지 않는 이미지 참조가 남아 있으면 안 된다."""
    found: dict[str, list[str]] = {}
    for record in corpus.records:
        dead = find_dead_image_refs(corpus._body(record))
        if dead:
            found[record["id"]] = dead[:3]
    assert not found, (
        f"번들에 죽은 이미지 링크가 남아 있다: {found} — 옛 스크립트로 빌드했거나 "
        f"새 글이 다른 양식을 쓴다. `uv run python scripts/build_index.py <정본경로>` 재실행"
    )


def test_bundle_keeps_image_descriptions_as_captions(corpus: Corpus):
    """링크를 버리면서 설명까지 버리면 안 된다 — alt 는 캡션으로 남아야 한다."""
    total = 0
    articles = 0
    for record in corpus.records:
        captions = _CAPTION.findall(corpus._body(record))
        if captions:
            articles += 1
            total += len(captions)
        assert all(c.strip() for c in captions), f"빈 캡션: {record['id']}"
    assert total >= MIN_CAPTIONS, f"캡션이 너무 적다({total}) — 변환이 빠진 채 빌드됐다"
    assert articles >= MIN_ARTICLES_WITH_CAPTION, f"캡션이 있는 글이 너무 적다({articles})"


def test_rendered_article_has_no_image_markup(corpus: Corpus):
    """에이전트에게 나가는 최종 응답에 깨진 이미지 문법이 섞이면 안 된다."""
    rendered = corpus.render_article("92")  # HTML <img>를 쓰던 글
    assert "<img" not in rendered.lower()
    assert "![" not in rendered
    assert "🖼️ **그림**:" in rendered


# --- 변환 단위 ---

def test_markdown_image_becomes_caption():
    out = strip_publishing_scaffolding("# T\n\n앞\n\n![도식 설명](assets/blog-03-x.png)\n\n뒤\n")
    assert out == "# T\n\n앞\n\n> 🖼️ **그림**: 도식 설명\n\n뒤"


def test_markdown_image_with_title_becomes_caption():
    out = strip_publishing_scaffolding('# T\n\n![도식 설명](assets/a.png "제목")\n')
    assert out == "# T\n\n> 🖼️ **그림**: 도식 설명"


def test_html_image_becomes_caption():
    """92·93번은 width를 주려고 HTML `<img>`를 쓴다 — 마크다운과 같이 다뤄야 한다."""
    src = '# T\n\n<img src="assets/blog-92-y.png" alt="상태 머신 도식" width="450" />\n'
    assert strip_publishing_scaffolding(src) == "# T\n\n> 🖼️ **그림**: 상태 머신 도식"


def test_empty_alt_image_is_dropped():
    """남길 설명이 없으면 죽은 링크만 남으므로 줄째 지운다."""
    out = strip_publishing_scaffolding("# T\n\n앞\n\n![](assets/a.png)\n\n뒤\n")
    assert out == "# T\n\n앞\n\n뒤"


def test_working_image_urls_are_kept():
    """절대 URL은 실제로 열린다 — 소스가 나중에 진짜 이미지를 쓰면 그대로 가야 한다."""
    src = "# T\n\n![살아있는](https://example.com/a.png)\n"
    assert strip_publishing_scaffolding(src) == src.strip()
    assert find_dead_image_refs(src) == []


def test_code_blocks_are_never_touched():
    """🔴 코드 블록 안의 이미지 문법은 글이 설명하는 예제다. 바꾸면 예제가 깨진다."""
    src = (
        "# T\n\n```markdown\n![예시](assets/a.png)\n```\n\n"
        '```html\n<img src="assets/b.png" alt="예시">\n```\n'
    )
    out = strip_publishing_scaffolding(src)
    assert "![예시](assets/a.png)" in out
    assert '<img src="assets/b.png" alt="예시">' in out
    assert "🖼️" not in out
    assert find_dead_image_refs(src) == []


def test_find_dead_image_refs_catches_inline_form():
    """변환은 단독 줄만 바꾼다 — 문장 중간에 낀 이미지는 프리플라이트가 잡아야 한다."""
    out = strip_publishing_scaffolding("# T\n\n문장 중간 ![인라인](assets/a.png) 뒤쪽\n")
    assert find_dead_image_refs(out) == ["![인라인](assets/a.png)"]


def test_conversion_is_idempotent():
    """번들 재빌드가 안정적이어야 한다 — 두 번 돌려도 같아야 한다."""
    src = "# T\n\n![도식](assets/a.png)\n\n<img src=\"assets/b.png\" alt=\"도식2\" />\n"
    once = strip_publishing_scaffolding(src)
    assert strip_publishing_scaffolding(once) == once
