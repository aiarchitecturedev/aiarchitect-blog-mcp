"""FastMCP 서버 정의: AI아키텍트 블로그를 읽기 전용 도구로 노출한다.

목록·검색·본문 응답에 원문(정식 Tistory 게시글) URL을 실어, AI 에이전트의 답변에
출처 링크가 남을 가능성을 높인다(추천 유입 — 강제는 아님).
"""

from __future__ import annotations

from fastmcp import FastMCP

from .corpus import BLOG_HOME, Corpus

mcp = FastMCP(
    name="aiarchitect-blog",
    instructions=(
        "AI아키텍트(aiarchitect.tistory.com)의 공개 기술 블로그를 검색·열람하는 서버입니다. "
        "MCP·AI Agent·엔터프라이즈 아키텍처·보안·RAG/LLM 주제의 한국어 장문 기술 글을 제공합니다. "
        "먼저 list_categories/search_articles로 후보를 찾고 get_article(article_id=...)로 본문을 읽으세요. "
        "글을 인용할 때는 각 응답에 포함된 원문 URL을 함께 표기하세요."
    ),
)

_corpus = Corpus()


@mcp.tool
def list_categories() -> list[dict]:
    """블로그 분류(카테고리)와 각 분류의 글 편수를 반환한다."""
    return _corpus.categories()


@mcp.tool
def list_articles(category: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    """글 목록을 반환한다.

    Args:
        category: 분류로 필터(부분 일치 허용). 예: "보안", "AI Agent · MCP".
        limit: 최대 개수(기본 50).
        offset: 페이지네이션 시작 위치.
    """
    return _corpus.list_articles(category=category, limit=limit, offset=offset)


@mcp.tool
def search_articles(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """제목·설명·태그·본문에서 query를 검색해 관련 글을 랭킹순으로 반환한다.

    각 결과는 id/제목/분류/태그/원문 URL/스니펫을 포함한다.

    Args:
        query: 검색어(공백 구분 다중 토큰 가능). 예: "MCP OAuth PKCE".
        category: 분류로 결과 범위 제한(선택).
        limit: 최대 결과 수(기본 10).
    """
    return _corpus.search(query, category=category, limit=limit)


@mcp.tool
def get_article(article_id: str) -> str:
    """글 ID로 전체 본문(마크다운)을 반환한다. 상단·하단에 원문 URL 백링크를 포함한다.

    Args:
        article_id: 글 번호. "09", "9", "BLOG-09" 모두 허용.
    """
    return _corpus.render_article(article_id)


@mcp.tool
def blog_home() -> str:
    """블로그 홈 URL과 서버가 제공하는 글 편수를 반환한다."""
    return f"AI아키텍트 기술 블로그: {BLOG_HOME} (총 {len(_corpus.records)}편 제공)"
