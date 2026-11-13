# 내 블로그를 MCP 서버로 공개하기: AI Agent 검색·출처 링크·PyPI 배포까지

기술 블로그의 공개 글 69편을 읽기 전용 MCP 서버로 묶어 AI 에이전트가 목록·검색·본문 조회를 할 수 있게 만든 과정입니다. 결정적 키워드 검색, 원문 URL 내장, 미게시 글 fail-closed 제외, self-contained wheel, uvx 실행과 PyPI v0.1.1 배포까지 실제 구현을 정리합니다.

![기술 블로그 문서가 self-contained Package와 읽기 전용 MCP Gateway로 배포되고 AI Client 결과가 원문 페이지로 다시 연결되는 구조](assets/blog-63-blog-mcp-publication-hero.png)

<div id="aiarchitect-toc" style="background-color: #f6f9fc; color: #263746;">
<p style="color: #263746;"><b>목차</b></p>
<ol style="list-style-type: decimal; color: #555555;">
<li style="color: #555555;"><a href="#ai-section-1">먼저 실행해 보기</a></li>
<li style="color: #555555;"><a href="#ai-section-2">왜 블로그를 MCP 서버로 만드는가</a></li>
<li style="color: #555555;"><a href="#ai-section-3">설계 원칙 — 작게, 읽기 전용으로, 결정적으로</a></li>
<li style="color: #555555;"><a href="#ai-section-4">다섯 개 도구로 탐색 흐름 만들기</a></li>
<li style="color: #555555;"><a href="#ai-section-5">임베딩 없이 시작하는 결정적 검색</a></li>
<li style="color: #555555;"><a href="#ai-section-6">원문 URL은 프롬프트가 아니라 데이터에 넣는다</a></li>
<li style="color: #555555;"><a href="#ai-section-7">미게시 글은 홈으로 보내지 말고 fail-closed로 제외한다</a></li>
<li style="color: #555555;"><a href="#ai-section-8">콘텐츠 스냅샷을 self-contained 패키지로 만들기</a></li>
<li style="color: #555555;"><a href="#ai-section-9">코드와 콘텐츠 라이선스를 분리한다</a></li>
<li style="color: #555555;"><a href="#ai-section-10">테스트는 프로토콜보다 배포 아티팩트까지 본다</a></li>
<li style="color: #555555;"><a href="#ai-section-11">이 구현에서 얻은 교훈</a></li>
<li style="color: #555555;"><a href="#ai-section-12">참고 자료</a></li>
</ol>
</div>


기술 블로그를 오래 쓰면 글은 쌓이지만, AI 에이전트가 그 글을 정확히 찾고 원문까지 연결하는 경로는 저절로 생기지 않습니다. 검색 엔진에 색인되기를 기다리는 대신, 공개 콘텐츠를 **모델 컨텍스트 프로토콜(Model Context Protocol, MCP)** 도구로 직접 제공하면 어떨까요?

저는 이 블로그의 공개 글을 목록·검색·본문 조회가 가능한 **읽기 전용 MCP 서버**로 만들고, 공개 저장소와 Python 패키지로 배포했습니다. 이 글을 개정한 2026년 8월 11일 기준으로 블로그에는 공개 글 78편이 있고, 공개 패키지 `aiarchitect-blog-mcp` v0.1.1에는 검증된 69편의 스냅샷이 들어 있습니다. 블로그 전체 편수와 패키지 편수가 다른 이유는 새 글을 곧바로 포함하지 않고, URL·메타데이터·배포 아티팩트 검증을 통과한 글만 릴리스하기 때문입니다.

**구현에서 실제로 고른 것** — 이 글은 단순한 아이디어가 아니라 실제 공개 버전의 설계와 배포 기록입니다. 핵심은 네 가지입니다.

1. 목록·검색·본문 조회만 제공하는 작은 읽기 전용 도구 표면
2. 임베딩 없이 시작하는 재현 가능한 키워드 검색
3. 모든 검색·본문 응답에 정식 원문 URL을 포함하는 구조
4. 미게시·비정상 URL 콘텐츠를 기본 거부하고, 검증된 스냅샷만 패키징하는 배포 절차

> **현재 공개 상태**
>
> | 항목 | 값 |
> | --- | --- |
> | 패키지 | `aiarchitect-blog-mcp` |
> | 버전 | `0.1.1` |
> | 번들 콘텐츠 | 정식 게시 URL을 가진 공개 글 69편 |
> | 전송 방식 | 로컬 `stdio` |
> | 실행 | `uvx aiarchitect-blog-mcp` |
> | 소스 | [GitHub 저장소](https://github.com/aiarchitecturedev/aiarchitect-blog-mcp) |
> | 원문 | [AI아키텍트 블로그](https://aiarchitect.tistory.com/) |

MCP 자체가 처음이라면 [MCP란 무엇인가](https://aiarchitect.tistory.com/2)를 먼저 읽어도 좋습니다.

## 1. 먼저 실행해 보기

`uv`가 설치돼 있다면 Claude Code에는 다음 한 줄로 등록할 수 있습니다.

```bash
claude mcp add aiarchitect-blog -- uvx aiarchitect-blog-mcp
```

Claude Desktop이나 Cursor처럼 JSON 설정을 사용하는 클라이언트는 다음과 같이 등록합니다.

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

`uvx`가 없다면 `pipx run aiarchitect-blog-mcp`로도 실행할 수 있습니다. 서버를 연결한 뒤에는 다음과 같이 자연어로 요청합니다.

```text
AI아키텍트 블로그에서 MCP OAuth 관련 글을 찾아줘.
가장 관련 있는 글의 핵심을 요약하고 원문 링크도 알려줘.
```

클라이언트는 `search_articles`로 후보를 찾고, 필요하면 `get_article`로 본문을 읽습니다. 별도의 벡터 DB나 API 키, 원본 저장소가 필요하지 않습니다.

## 2. 왜 블로그를 MCP 서버로 만드는가

블로그를 MCP 서버로 노출하면 세 가지 효과를 기대할 수 있습니다.

| 목적 | 내용 |
| --- | --- |
| 탐색 가능성 | 에이전트가 자연어 질의로 콘텐츠 목록·검색·본문을 직접 조회 |
| 출처 연결 | 도구 응답에 정식 원문 URL을 실어 답변에 출처가 남을 가능성을 높임 |
| 도그푸딩 | MCP 설계를 자신의 실제 콘텐츠로 검증하고 운영 경험을 축적 |

이 패턴은 블로그에만 한정되지 않습니다. 공개 문서, FAQ, 릴리스 노트, 오픈 API 레퍼런스처럼 **외부에 공개해도 되고 재배포 권한이 명확한 텍스트 묶음**에도 적용할 수 있습니다.

다만 두 가지는 구분해야 합니다. 첫째, 웹에서 공개 열람할 수 있다는 사실이 패키지로 재배포할 권리를 자동으로 주지는 않습니다. 둘째, 공개 데이터 MCP와 고객·사내 문서를 다루는 비공개 MCP는 인증·인가·테넌트 격리 관점에서 전혀 다른 시스템입니다. 이 프로젝트는 제가 권리를 가진 공개 글만 대상으로 합니다.

![Blog Markdown과 공개 URL 스냅샷을 self-contained Package와 읽기 전용 MCP로 배포하고 AI Client를 Source Link로 원문에 연결하는 구조](assets/blog-63-blog-mcp-publication-architecture.png)

*그림 1. 검증된 공개 글 스냅샷을 실행 가능한 Package에 포함하고 읽기 전용 MCP 응답이 원문 URL을 유지하게 하는 배포 구조*

## 3. 설계 원칙 — 작게, 읽기 전용으로, 결정적으로

구현 전에 네 가지 원칙을 정했습니다.

1. **읽기 전용(Read-only)** — 목록·검색·본문 조회만 제공하고 쓰기·수정·삭제 도구는 두지 않습니다.
2. **작은 도구 표면** — 에이전트가 넓게 탐색한 뒤 좁혀 갈 수 있는 5개 도구만 제공합니다.
3. **결정적 검색 우선(Deterministic first)** — 69편 규모에서는 임베딩·벡터 DB보다 단순하고 재현 가능한 키워드 랭킹을 먼저 사용합니다.
4. **출처 링크 내장(Source link by construction)** — 프롬프트에만 의존하지 않고 목록·검색·본문 데이터 자체에 원문 URL을 넣습니다.

이 원칙 덕분에 실행 중 외부 네트워크나 데이터베이스가 필요 없는 정적 읽기 서비스가 됩니다.

## 4. 다섯 개 도구로 탐색 흐름 만들기

공개 v0.1.1은 다음 다섯 도구를 제공합니다.

| 도구 | 역할 | 주요 반환값 |
| --- | --- | --- |
| `list_categories` | 분류와 편수 개관 | 분류별 `count` |
| `list_articles` | 분류·페이지 기준 목록 | id·제목·태그·URL |
| `search_articles` | 키워드 랭킹 검색 | 요약·점수·스니펫·URL |
| `get_article` | 글 전체 열람 | 원문 URL로 감싼 마크다운 |
| `blog_home` | 블로그 홈과 제공 편수 | 홈 URL·번들 편수 |

서버 골격은 작습니다.

```python
from fastmcp import FastMCP
from .corpus import BLOG_HOME, Corpus

mcp = FastMCP(
    name="aiarchitect-blog",
    instructions=(
        "공개 기술 블로그를 검색·열람하는 서버입니다. "
        "먼저 list_categories/search_articles로 후보를 찾고 "
        "get_article(article_id=...)로 본문을 읽으세요. "
        "인용할 때는 응답에 포함된 원문 URL을 함께 표기하세요."
    ),
)
corpus = Corpus()
readonly = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}

@mcp.tool(annotations=readonly)
def search_articles(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    return corpus.search(query, category=category, limit=limit)

def main() -> None:
    mcp.run()
```

`readOnlyHint`와 `openWorldHint`는 클라이언트가 도구의 성격을 이해하도록 돕는 힌트입니다. 실제 보안을 대신하지는 않지만, 정적 로컬 코퍼스만 읽는다는 계약을 기계적으로 표현합니다.

## 5. 임베딩 없이 시작하는 결정적 검색

검색은 제목·태그·설명·본문에 서로 다른 가중치를 주는 방식으로 시작했습니다. 제목 일치가 가장 강하고, 태그·설명·본문 순으로 가중치를 낮춥니다.

```python
def search(self, query, category=None, limit=10):
    terms = [t for t in query.lower().split() if t]
    scored = []

    for article in self.records:
        if category and category not in article["category"]:
            continue

        title = article["title"].lower()
        tags = " ".join(article["tags"]).lower()
        desc = article["description"].lower()
        body = self._body(article).lower()

        score = sum(
            title.count(term) * 5
            + tags.count(term) * 4
            + desc.count(term) * 3
            + body.count(term)
            for term in terms
        )
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return self._to_results(scored[:limit])
```

장점은 같은 코퍼스와 질의에 항상 같은 결과가 나온다는 것입니다. 동점 순서까지 글 ID로 고정할 수 있어 골든 테스트를 만들기 쉽습니다. 반면 의미가 비슷한 표현을 찾는 능력은 제한적이고, 긴 본문이나 반복 단어에 점수가 치우칠 수 있습니다.

따라서 지금 규모에서는 이 방식이 합리적이지만, 글이 수백·수천 편으로 늘면 키워드 검색을 1차 후보 생성기로 두고 임베딩 재랭킹을 추가하는 방식이 자연스럽습니다. 처음부터 벡터 DB를 도입하는 것보다 실패 지점과 운영 비용이 적습니다.

![list_categories와 search_articles로 후보를 찾고 Article ID로 get_article을 조회해 Source URL을 반환하며 미게시 글은 fail-closed로 제외하는 흐름](assets/blog-63-blog-mcp-deterministic-query-flow.png)

*그림 2. 결정적 목록·검색·본문 조회를 단계적으로 좁히고 정식 URL이 없는 콘텐츠는 결과에서 제외하는 읽기 흐름*

## 6. 원문 URL은 프롬프트가 아니라 데이터에 넣는다

이 서버의 중요한 설계는 `get_article`이 본문만 반환하지 않는다는 점입니다. 정식 원문 URL을 본문의 앞과 뒤에 구조적으로 포함합니다.

```python
def render_article(self, article_id: str) -> str:
    article = self._by_id.get(self._normalize_id(article_id))
    if not article:
        return "글을 찾을 수 없습니다. search_articles로 id를 확인하세요."

    header = (
        f"# {article['title']}\n\n"
        f"> 원문(정식 게시글): {article['url']}\n"
        f"> 분류: {article['category']}\n\n---\n\n"
    )
    footer = (
        f"\n\n---\n원문: {article['url']}\n"
        f"블로그: {BLOG_HOME}\n"
    )
    return header + self._body(article) + footer
```

여기에 서버 `instructions`가 “인용할 때 원문 URL을 함께 표기하라”고 안내합니다. 데이터와 지시를 두 겹으로 배치해 출처 링크가 최종 답변에 남을 가능성을 높입니다.

하지만 **인용을 강제할 수는 없습니다.** MCP 도구 결과와 서버 안내는 모델·클라이언트에 제공되는 입력일 뿐, 최종 답변의 형식을 통제하지 않습니다. 이 링크는 AI 답변에서 발생할 수 있는 추천 유입이지, 검색 엔진이 평가하는 SEO 백링크와도 다릅니다. 실제 유입 효과는 분석 도구에서 추천 도메인과 클릭을 측정해야 합니다.

## 7. 미게시 글은 홈으로 보내지 말고 fail-closed로 제외한다

초기 로컬 구현에는 공개 URL이 없으면 블로그 홈으로 대신 연결하는 폴백이 있었습니다. 링크가 깨지는 것은 막았지만, 홈은 해당 글의 원문이 아닙니다. 더 큰 문제는 미게시 원고가 목록과 검색에 노출될 수 있다는 점입니다.

공개 버전에서는 다음 조건을 모두 만족한 글만 코퍼스에 포함합니다.

```python
from urllib.parse import urlparse

ALLOWED_HOST = "aiarchitect.tistory.com"

def is_published(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    article_id = parsed.path.strip("/")
    return (
        parsed.scheme == "https"
        and parsed.netloc == ALLOWED_HOST
        and article_id.isascii()
        and article_id.isdigit()
        and int(article_id) > 0
    )
```

빈 URL, 홈 URL, 외부 도메인, 숫자가 아닌 경로, 비정상 글 번호는 모두 거부합니다. 인덱스의 `published` 플래그도 엄격히 `True`인 경우에만 통과시킵니다. 결과적으로 v0.1.1 번들의 69편은 모두 고유한 정식 게시글 URL을 가집니다.

이 규칙은 단순한 데이터 정리가 아니라 **출처 정확성에 대한 보안 경계**입니다. 불확실한 콘텐츠는 적당한 링크로 대체하지 않고 노출하지 않는 편이 안전합니다.

## 8. 콘텐츠 스냅샷을 self-contained 패키지로 만들기

서버가 실행할 때 원본 블로그나 작업 저장소를 읽으면 네트워크 장애와 경로 차이 때문에 재현성이 떨어집니다. 그래서 빌드 단계에서 검증된 인덱스와 본문 스냅샷을 패키지 안에 넣습니다.

```text
공개 블로그 마크다운
        │  build_index.py · 공개 URL 검증 · 메타데이터 정리
        ▼
src/aiarchitect_blog_mcp/data/
   ├─ articles_index.json
   └─ articles/*.md
        │  wheel/sdist 생성 · 아티팩트 검사
        ▼
PyPI: aiarchitect-blog-mcp 0.1.1
```

빌드 과정은 다음 불변 조건을 검사합니다.

- 기대한 글 ID 집합과 실제 파일 집합이 일치하는가
- ID와 원문 URL이 중복되지 않는가
- 모든 URL이 허용한 HTTPS 개별 게시글 형식인가
- 인덱스 편수와 번들 본문 파일 수가 같은가
- 작성용 메타데이터와 로컬 경로가 배포 본문에서 제거됐는가
- 기존 데이터가 불완전한 새 빌드로 덮어써지지 않는가

이렇게 만든 wheel은 원본 저장소 없이 동작합니다. 설치 시 `fastmcp` 같은 런타임 의존성은 필요하지만, 콘텐츠 조회를 위해 블로그에 다시 접속하지는 않습니다. 패키지 스냅샷이 실시간 블로그보다 늦을 수 있는 것은 이 검증 단계를 릴리스 경계로 선택했기 때문입니다.

## 9. 코드와 콘텐츠 라이선스를 분리한다

소스 코드를 공개한다고 해서 번들된 글 본문까지 같은 조건으로 자유롭게 재사용되는 것은 아닙니다. 이 프로젝트는 패키지 라이선스를 다음처럼 분리했습니다.

```text
MIT AND LicenseRef-AIArchitect-Articles
```

- 서버 코드: MIT
- 번들된 글 본문: `LicenseRef-AIArchitect-Articles`

원문 페이지가 정본이며, 콘텐츠의 분리 재배포·2차 저작·상업적 재이용 조건은 별도 문서로 명시합니다. 다른 사람의 블로그나 문서를 같은 방식으로 묶으려면 기술 구현보다 먼저 저작권과 이용 약관을 확인해야 합니다.

## 10. 테스트는 프로토콜보다 배포 아티팩트까지 본다

결정적 검색은 테스트하기 쉽습니다. 공개 버전에서는 다음 계약을 고정합니다.

```python
def test_search_finds_expected_article():
    results = corpus.search("MCP OAuth PKCE", limit=5)
    assert "09" in {item["id"] for item in results}

def test_article_contains_exact_source_url_twice():
    rendered = corpus.render_article("09")
    assert rendered.count("https://aiarchitect.tistory.com/11") >= 2

def test_no_home_fallback_is_served():
    assert all(is_published(item["url"]) for item in corpus.records)
```

여기에 69편 인덱스와 69개 본문 파일의 일치, 7개 분류별 편수, 입력 범위 클램프, 패키지 설치 후 `stdio` 기동까지 확인합니다. 중요한 점은 소스 트리의 테스트만 통과하는 데서 끝내지 않고, 실제로 배포할 wheel과 sdist의 파일 목록·메타데이터·라이선스를 검사하는 것입니다.

프로토콜 왕복이 성공해도 자연어 요청에서 올바른 도구가 선택되는지, 최종 답변에 출처 링크가 표시되는지는 별도 계층입니다. 그 부분은 실제 클라이언트 시나리오와 유입 분석으로 검증해야 합니다.

## 11. 이 구현에서 얻은 교훈

```text
[공개 v0.1.1 완료]
[x] 읽기 전용 5개 도구
[x] readOnlyHint · idempotentHint · openWorldHint 선언
[x] 결정적 키워드 검색과 골든 테스트
[x] 정식 게시 URL 없는 글 fail-closed 제외
[x] 인덱스·본문을 self-contained wheel에 번들
[x] 입력 limit·offset 방어적 범위 처리
[x] 코드와 콘텐츠 라이선스 분리
[x] uvx로 실행 가능한 PyPI 패키지 배포
[x] wheel·sdist 설치 및 stdio 스모크 검증

[계속 측정할 항목]
[ ] AI 클라이언트별 도구 선택 성공률
[ ] 최종 답변의 원문 URL 표시율
[ ] 추천 도메인별 실제 블로그 유입
[ ] 새 글을 번들에 반영하는 릴리스 주기
```

가장 큰 교훈은 **공개 콘텐츠를 MCP로 노출하는 일보다, 무엇을 공개했다고 믿을 수 있게 만드는 일이 더 중요하다**는 점입니다. 작은 읽기 전용 서버와 단순한 검색으로 시작할 수 있지만, 원문 URL 검증·미게시 글 제외·아티팩트 검사·라이선스 분리가 있어야 다른 사람이 안심하고 실행할 수 있습니다.

그리고 출처 링크는 유입을 보장하는 장치가 아닙니다. 다만 에이전트가 원문을 정확히 발견하고 링크할 수 있는 구조를 제공한다는 점에서, 검색 엔진 외에 하나의 새로운 콘텐츠 유통 경로를 만드는 실험으로는 충분한 가치가 있습니다.

직접 실행하거나 코드를 확인하려면 아래 세 곳을 보시면 됩니다. 글에서 설명한 도구 5개, 결정적 검색, fail-closed 제외, self-contained 번들이 모두 실제로 배포된 패키지 안에 있습니다.

| 확인할 것 | 위치 |
|---|---|
| 설치·실행 가능한 패키지 | [PyPI `aiarchitect-blog-mcp`](https://pypi.org/project/aiarchitect-blog-mcp/) |
| 소스 코드와 테스트 (MIT) | [GitHub 저장소](https://github.com/aiarchitecturedev/aiarchitect-blog-mcp) |
| MCP 서버 디렉터리 등록 | [Glama 등록 페이지](https://glama.ai/mcp/servers/aiarchitecturedev/aiarchitect-blog-mcp) |

이어지는 배포 하드닝 과정은 [오픈소스 MCP 서버 공개 배포 체크리스트](https://aiarchitect.tistory.com/68)에 정리했습니다.

## 12. 참고 자료

- [Model Context Protocol — Architecture](https://modelcontextprotocol.io/docs/learn/architecture) · Host·Client·Server 역할과 전송 계층
- [Model Context Protocol — Tools](https://modelcontextprotocol.io/docs/learn/server-concepts) · Tool 선언과 `readOnlyHint`·`idempotentHint`·`openWorldHint` 주석
- [Python Packaging — Writing your `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) · wheel·sdist 메타데이터와 패키지 데이터 포함 규칙
- [uv — Running tools with `uvx`](https://docs.astral.sh/uv/guides/tools/) · 설치 없이 실행하는 도구 배포 경로

함께 읽으면 좋은 글: [MCP란 무엇인가](https://aiarchitect.tistory.com/2), [MCP Tool 설계 원칙](https://aiarchitect.tistory.com/3), [MCP OAuth 2.1 인증 구조](https://aiarchitect.tistory.com/11), [MCP Server 보안 체크리스트](https://aiarchitect.tistory.com/22), [자연어에서 MCP Tool Call까지: 통합 테스트](https://aiarchitect.tistory.com/14).
