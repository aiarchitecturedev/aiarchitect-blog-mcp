# AI아키텍트 블로그 MCP 서버

[aiarchitect.tistory.com](https://aiarchitect.tistory.com/) 의 공개 기술 블로그(현재 번들 **49편 규모**)를
**MCP(Model Context Protocol) 도구**로 노출합니다. Claude·Cursor 등 MCP 클라이언트에 붙이면
AI 에이전트가 MCP·AI Agent·엔터프라이즈 아키텍처·보안·RAG/LLM 주제의 한국어 장문 기술 글을
바로 검색·열람할 수 있습니다.

> 💡 목록·검색·본문 응답에 **원문(정식 게시글) URL**이 실려, 에이전트의 답변에 출처 링크가 남을
> 가능성을 높입니다(추천 유입). ※ 현재 로컬 번들에는 정식 게시 URL이 아직 없는 후보 원고 2편이
> 블로그 홈 URL로 폴백돼 있어, **공개 배포 빌드에서는 제외 대상**입니다.

## 🔧 제공 도구

| 도구 | 설명 |
|------|------|
| `list_categories()` | 분류(7종)와 각 편수 |
| `list_articles(category?, limit?, offset?)` | 글 목록(분류 필터·페이지네이션) |
| `search_articles(query, category?, limit?)` | 제목·설명·태그·본문 키워드 검색(랭킹·스니펫) |
| `get_article(article_id)` | 전체 본문(마크다운) + 원문 URL(출처 링크) |
| `blog_home()` | 블로그 홈 URL·제공 편수 |

## 🚀 설치

### Claude Code
```bash
claude mcp add aiarchitect-blog -- uvx aiarchitect-blog-mcp
```

### Claude Desktop / Cursor (`mcp.json`)
```json
{
  "mcpServers": {
    "aiarchitect-blog": {
      "command": "uvx",
      "args": ["aiarchitect-blog-mcp"]
    }
  }
}
```

`uvx`가 없으면 [uv](https://docs.astral.sh/uv/)를 설치하거나 `pipx run aiarchitect-blog-mcp` 를 사용하세요.

## 🛠️ 로컬 개발

```bash
uv sync                              # 의존성 설치
python scripts/build_index.py        # 블로그 md → data/articles_index.json + 본문 번들
uv run pytest -q                     # 파서·검색 골든 테스트
uv run aiarchitect-blog-mcp          # stdio 서버 실행
```

`build_index.py`는 기본적으로 `../github-portfolio-public/aiarchitect/blogs/*.md` 를 읽습니다.
다른 경로면 인자로 넘기세요: `python scripts/build_index.py /path/to/blogs`.

## 📚 다루는 주제

MCP 설계·OAuth 2.1·원격 MCP · AI Agent 보안/감사 · RAG·STT·화자분리 · 멀티플랫폼 SDK 아키텍처 ·
골든 테스트·시크릿 가드 등. 전체 목록은 [블로그](https://aiarchitect.tistory.com/)에서 확인하세요.

## 📄 라이선스

**코드는 MIT.** 번들된 **글 본문의 저작권은 원저자(AI아키텍트)**에게 있으며(코드 라이선스와 별개 —
재배포·2차 이용 조건은 별도), 본 서버는 공개 게시글을 편의상 재노출합니다.
