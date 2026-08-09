# 내 블로그를 MCP 서버로 만들기: 공개 콘텐츠를 AI 도구로 노출하고 출처 링크로 유입을 유도하기

기술 블로그를 오래 쓰다 보면 글은 쌓이는데, 정작 요즘 사람들이 정보를 찾는 창구인 **AI 에이전트 (AI Agent)** 는 내 글을 잘 데려오지 못합니다. 검색 색인에 잡히기를 기다리거나, 누군가 링크를 붙여 주기를 기다릴 뿐입니다. 그런데 내가 이미 가진 것은 **잘 구조화된 공개 콘텐츠 코퍼스 (Corpus)** 입니다. 이걸 에이전트가 도구로 직접 검색·열람하게 만들면 어떨까요?

이 글은 제가 이 블로그(49편 규모)를 **모델 컨텍스트 프로토콜 (Model Context Protocol, MCP)** 읽기 전용 서버로 **만들고 로컬에서 검증한** 과정을 정리합니다. 여기서 다루는 범위는 **로컬 표준입출력(stdio) 서버로 만들어 동작을 확인하는 단계**까지입니다. 공개 저장소·패키지 레지스트리·원격 서버로의 **공개 배포는 별도 승인 후 진행할 후속 단계**이며, 그 전에 필요한 보안·필터링 작업을 이 글에서 함께 짚습니다. 핵심 아이디어는 두 가지입니다. 첫째, **작은 읽기 전용 도구 표면**으로 목록·검색·본문만 노출한다. 둘째, **응답에 원문(정식 게시글) URL을 실어**, 에이전트가 답변에 출처를 남길 **가능성을 높여** 블로그로의 **추천 유입(Referral)** 을 유도한다. 강제는 아니지만, 콘텐츠가 그 자체로 노출 채널이자 유입 경로가 됩니다.

이 글의 코드는 실제 서버를 바탕으로 하되, 어느 공개 콘텐츠 코퍼스에도 적용할 수 있도록 일반화·축약한 예시입니다. **아래 파이썬 코드 블록은 `# 현재 로컬 구현`과 `# 공개 배포 전 목표(미반영)`로 구분해 표시**하니, 동작이 확인된 부분과 앞으로 할 계획을 나눠 읽어 주세요(설정·명령 예시 블록은 별도). 초안 본문에는 특정 회사·고객·제품·계정·내부 URL·저장소 식별자를 포함하지 않습니다. 다만 솔직히 밝히면, **현재 로컬 검증 번들에는 URL 메타데이터가 불완전한 2편**(공개본이지만 로컬 미러의 상태·URL이 오래된 1편 + 미게시 후보 1편)이 블로그 홈 URL로 폴백돼 포함돼 있어, 이 번들 자체는 아직 공개 배포 가능한 상태가 아닙니다(공개용 빌드에서 제외하는 방법은 6절). 또 "공개 열람 가능"과 "패키지로 재배포 가능"은 다르므로, 재배포 시 **코드 라이선스(예: MIT)와 글 본문의 이용 조건(예: CC BY 같은 별도 명시)을 구분**해야 합니다(이 글은 제 글로 한정합니다). MCP·라이브러리 API는 버전에 따라 달라지므로, 개념을 먼저 이해하고 각 도구의 최신 공식 문서([MCP 사양](https://modelcontextprotocol.io/), [FastMCP](https://gofastmcp.com/), [Hatch](https://hatch.pypa.io/))로 확인하시기 바랍니다. MCP 자체가 처음이라면 [MCP란 무엇인가](https://aiarchitect.tistory.com/2)를 먼저 읽으면 좋습니다.

## 1. 왜 블로그를 MCP 서버로 만드는가

블로그를 MCP 서버로 노출하면 세 가지를 동시에 노립니다.

| 목적 | 내용 |
| --- | --- |
| 노출(Distribution) | 에이전트가 자연어로 "그 주제 글 찾아줘"만 해도 내 코퍼스에서 검색·열람 |
| 추천 유입(Referral) | 응답에 원문 URL이 실려, 답변에 출처가 남을수록 블로그로 유입될 여지가 생김 |
| 차별화·도그푸딩(Dogfooding) | "내 콘텐츠를 내가 만든 MCP 서버로 노출한다"는 사례 자체가 콘텐츠가 됨 |

블로그가 아니어도 됩니다. **공개 문서·FAQ·릴리스 노트·오픈 API 레퍼런스**처럼 "공개해도 되는, 잘 구조화된 텍스트 묶음"이면 같은 패턴이 적용됩니다. 다만 **공개 열람이 곧 재배포 허용은 아닙니다.** 서버가 본문을 패키지에 담아 배포한다면, 그 콘텐츠의 라이선스·약관·삭제 요청을 존중할 수 있어야 합니다. 또 처음부터 공개인 데이터와, 인가·테넌트 격리가 필요한 비공개 데이터는 완전히 다른 문제입니다([멀티테넌트 RAG 보안](https://aiarchitect.tistory.com/25) 참고). 이 글의 공개 배포 목표 범위는 **재배포 가능한 공개 글**에 한정합니다(앞서 밝혔듯 현재 로컬 검증 번들에는 예외적으로 홈 URL로 폴백된 2편이 포함돼 있습니다).

## 2. 설계 원칙 — 작게, 읽기 전용으로, 결정적으로

구현에 앞서 네 가지 원칙을 정했습니다.

1. **읽기 전용 (Read-only)** — 도구는 목록·검색·본문 조회만 한다. 쓰기·삭제가 없으니, 이 공개 정적 데이터 조건에서는 승인·부작용·롤백 부담이 작다(읽기라도 비용·개인정보·감사 이슈가 아예 없지는 않다). 공격 표면도 작아진다.
2. **작은 도구 표면** — 도구는 5개면 충분하다. 에이전트가 "넓게 → 좁게"로 탐색하도록, 분류 나열 → 목록 → 검색 → 본문 순의 최소 집합만 노출한다([MCP Tool 설계 원칙](https://aiarchitect.tistory.com/3)).
3. **결정적 검색 우선 (Deterministic first)** — 처음부터 임베딩·벡터 DB를 쓰지 않는다. 49편 규모에서는 결정적 키워드 랭킹이 더 빠르고, 재현 가능하고, 인프라가 필요 없다. 규모가 커지면 그때 임베딩을 얹는다.
4. **출처 링크를 응답에 내장 (Source link by construction)** — "인용해 주세요"라고 부탁하는 대신, 본문 응답의 상단·하단에 원문 URL을 **구조적으로** 넣어 노출 가능성을 높인다. 다만 이것이 인용을 **강제하지는 못한다**(뒤 7절에서 한계를 명확히 한다).

이 원칙들 덕분에 서버는 **외부 네트워크·DB가 없는 정적 읽기 서비스**가 됩니다(파일 읽기와 본문 캐시 상태는 있어 완전한 순수 함수는 아닙니다).

## 3. 도구 표면과 최소 실행 골격

런타임은 파이썬(Python, 3.10 이상)과 `fastmcp`를 썼습니다. 도구는 데코레이터로 선언하고, 함수 시그니처와 독스트링이 그대로 입력 스키마·설명이 됩니다.

```python
# 현재 로컬 구현(축약)
from fastmcp import FastMCP
from .corpus import BLOG_HOME, Corpus

mcp = FastMCP(
    name="aiarchitect-blog",
    instructions=(
        "공개 기술 블로그를 검색·열람하는 서버입니다. "
        "먼저 list_categories/search_articles로 후보를 찾고 "
        "get_article(article_id=...)로 본문을 읽으세요. "
        "인용할 때는 각 응답에 포함된 원문 URL을 함께 표기하세요."
    ),
)
_corpus = Corpus()

@mcp.tool
def list_categories() -> list[dict]:
    """블로그 분류와 각 분류의 글 편수를 반환한다."""
    return _corpus.categories()

@mcp.tool
def search_articles(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """제목·설명·태그·본문에서 query를 검색해 관련 글을 랭킹순으로 반환한다.
    각 결과는 id/제목/분류/태그/원문 URL/점수/스니펫을 포함한다."""
    return _corpus.search(query, category=category, limit=limit)

@mcp.tool
def get_article(article_id: str) -> str:
    """글 ID로 전체 본문을 반환한다. 상단·하단에 원문 URL을 포함한다.
    article_id는 "09", "9", "BLOG-09"를 모두 허용한다."""
    return _corpus.render_article(article_id)

def main() -> None:
    mcp.run()   # 인자 없이 실행하면 기본 전송은 stdio

if __name__ == "__main__":
    main()
```

여기에 `list_articles`(분류 필터 목록)와 `blog_home`(홈 URL·총 편수)까지 더해 **다섯 도구**를 **탐색 흐름** 순으로 배치한 것이 핵심입니다.

| 도구 | 역할 | 반환 |
| --- | --- | --- |
| `list_categories` | 분류와 편수 개관 | 분류별 count(URL 없음) |
| `list_articles` | 분류로 필터해 목록 | id·제목·태그·URL 요약 |
| `search_articles` | 키워드로 랭킹 검색 | 요약 + 점수 + 스니펫 |
| `get_article` | 본문 전체 열람 | 원문 URL이 감싼 마크다운 |
| `blog_home` | 홈 URL·총 편수 | 한 줄 안내 |

`main()`을 콘솔 엔트리포인트로 등록하면(`[project.scripts]`), 설치 후 실행 파일 하나로 서버가 뜹니다. 로컬 소스에서 바로 띄워 클라이언트에 붙이는 방법은 8절에서 다룹니다. 서버 수준 `instructions`에 "먼저 검색, 다음 본문, 인용 시 URL 표기"라는 **사용 순서와 인용 안내**를 적어 두면, 에이전트가 도구를 올바른 순서로 쓰고 원문 URL을 함께 노출할 확률이 올라갑니다(강제가 아니라 안내입니다). 도구 이름을 동사+목적어로, 설명을 짧고 구체적으로 쓰는 원칙은 [MCP Tool 설계 원칙](https://aiarchitect.tistory.com/3)에서 다뤘습니다.

## 4. 코퍼스 파서 — 헤더 여러 변형을 흡수한다

가장 현실적인 문제는 **원본 마크다운의 헤더가 제각각**이라는 점이었습니다. 초안·게시본·확장 시리즈가 각기 다른 머리말(문서 ID, 상태, 공개 URL, 권장 제목, 태그…)을 쓰고 있었습니다. 그래서 파서는 **알려진 필드명만 화이트리스트로 뽑는** 방식으로 여러 변형을 흡수합니다.

```python
# 현재 로컬 구현(축약)
_META_KEYS = {
    "문서 ID", "상태", "Tistory 상태", "분류", "공개일", "공개 URL",
    "제목", "권장 제목", "검색 설명", "태그", "권장 태그", ...
}
_BULLET = re.compile(r"^-\s*([^:：]+?)\s*[:：]\s*(.*)$")

def parse_metadata(text: str) -> dict[str, str]:
    """상단 bullet 헤더에서 '알려진 필드'만 추출한다(첫 등장 우선)."""
    fields = {}
    for ln in text.splitlines()[:30]:          # 상단 30줄만 스캔(휴리스틱)
        m = _BULLET.match(ln)
        if m and (key := m.group(1).strip("` ")) in _META_KEYS and key not in fields:
            fields[key] = m.group(2).strip()
    return fields
```

두 가지 방어가 있습니다. 값은 **화이트리스트 키만** 취하고, 스캔은 **상단 30줄**로 제한합니다. 다만 이 "상단 N줄" 규칙은 **완전한 헤더 경계 보장이 아니라 휴리스틱**입니다. 본문이 30줄 안에서 시작하면서 `- 상태:` 같은 화이트리스트 키를 우연히 포함하면 본문 일부가 헤더로 오인될 수 있고, 반대로 메타가 하나도 없으면 H1이 제거되지 않습니다. 운영에서는 **명시적 종료 구분자(`---`)나 YAML 프론트매터로 헤더 경계를 확정**하고, 필수 필드·중복 문서 ID 검증을 추가하는 편이 안전합니다.

**공개 URL이 아직 없는 글**(발급 전 초안)은 링크가 깨지면 안 됩니다. 지금 구현은 URL이 없거나 `http`로 시작하지 않으면 **블로그 홈으로 폴백**합니다.

```python
# 현재 로컬 구현(축약)
url = fields.get("공개 URL", "").strip("` ")
if not url or "미발급" in url or not url.startswith("http"):
    url = BLOG_HOME     # 임시 방편: 홈으로 폴백
```

주의할 점이 둘 있습니다. 첫째, **홈은 그 글의 원문이 아닙니다** — 폴백은 깨진 개별 링크를 피할 뿐, "정식 원문"을 보장하지 않습니다. 둘째, `startswith("http")`는 URL의 형식·생존을 검증하지 않아 `httpx...` 같은 문자열도 통과합니다. 그래서 **공개 배포로 넘어가기 전에는** 폴백이 아니라 **실패 폐쇄(Fail-closed)** 로 바꿔야 합니다. 즉 (1) 상태가 공개 완료가 아니거나 (2) `urlparse()`로 `scheme=="https"`와 허용 호스트를 통과하는 개별 게시글 URL이 없으면 **인덱스에서 제외**하고, 필요하면 빌드를 실패시킵니다. 이렇게 해야 미게시 원고가 검색·본문·패키지 어디에도 새지 않습니다(6절과 연결).

## 5. 검색 — 임베딩 없이 시작하는 결정적 랭킹

49편 규모에서는 임베딩·벡터 DB가 과합니다. 대신 **필드 가중치 기반의 결정적 랭킹**을 씁니다. 제목 일치가 가장 세고, 태그·설명·본문 순으로 가중치를 낮춥니다. 각 결과에는 점수와 스니펫을 함께 붙입니다.

```python
# 현재 로컬 구현(축약)
def search(self, query, category=None, limit=10):
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    if not terms:
        return []
    scored = []
    for r in self.records:
        if category and category not in r["category"]:
            continue
        title, tags = r["title"].lower(), " ".join(r["tags"]).lower()
        desc, body = r["description"].lower(), self._body(r).lower()
        score = sum(title.count(t) * 5 + tags.count(t) * 4
                    + desc.count(t) * 3 + body.count(t) for t in terms)
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))     # 점수 desc, 동점은 id asc
    out = []
    for score, r in scored[:limit]:
        item = self._summary(r)
        item["score"] = score                          # 점수를 명시적으로 실어 준다
        item["snippet"] = self._snippet(r, terms)
        out.append(item)
    return out
```

이 방식의 장점은 **결정적**이라는 것입니다. 같은 코퍼스·같은 질의에는 항상 같은 순서가 나오고, 동점은 `id` 오름차순으로 못 박아 순서가 흔들리지 않습니다. 그래서 "질의 X → 상위에 글 Y"를 **테스트로 고정**할 수 있습니다(10절). 다만 **결정적이라는 것과 관련성이 우수하다는 것은 다릅니다.** 이 방식은 부분 문자열 출현 횟수를 더하는 OR 검색이라, 긴 본문이나 반복 단어에 점수가 편향되고, 같은 질의어를 중복해 넣으면 중복 가산됩니다. 규모가 수백 편을 넘으면 이 결정적 랭킹을 1차 필터로 두고 그 위에 임베딩 재랭킹을 얹는 2단 구성으로 확장하는 것이 자연스럽습니다. 그때의 중복·재색인 함정은 [RAG 멱등 인덱싱](https://aiarchitect.tistory.com/9)에서 다뤘습니다.

## 6. 빌드와 번들 — 콘텐츠 스냅샷을 패키지에 담기

서버가 실행 시점에 원본 저장소를 읽어야 한다면 배포가 번거로워집니다. 그래서 **빌드 단계에서 인덱스와 본문 스냅샷을 패키지 안으로 굽습니다.** 빌드 스크립트는 공개 마크다운을 파싱해 `articles_index.json`을 만들고, 본문 파일을 패키지의 `data/` 아래로 복사합니다.

```text
공개 블로그 마크다운(*.md)
        │  scripts/build_index.py  (패키징 전에 명시적으로 실행)
        ▼
src/<pkg>/data/
   ├─ articles_index.json   ← 메타데이터 인덱스(제목·분류·태그·URL)
   └─ articles/*.md         ← 본문 스냅샷(검색·열람용)
```

```python
# 공개 배포 전 목표 구현(미반영) — 현재 build_index.py는 모든 파일을 인덱싱하고
# URL 없는 글은 홈으로 폴백한다. 아래처럼 '기본 거부(fail-closed)' 술어로 바꿔야 한다.
# (전제: build_record()가 rec['status']를 채우도록 함께 확장해야 한다 — 현재 레코드엔 status 없음)
from urllib.parse import urlparse
ALLOWED_HOST = "aiarchitect.tistory.com"

def is_publicly_published(rec) -> bool:
    """공개 완료 상태 + 홈이 아닌 개별 https 게시글 URL만 통과(그 외는 모두 거부)."""
    if rec.get("status") != "공개 완료":
        return False
    u = urlparse(rec.get("url", ""))
    return (u.scheme == "https" and u.netloc == ALLOWED_HOST
            and u.path.strip("/").isdigit())          # 예: /61 같은 개별 글 경로만

records, articles_dir = [], OUT_DIR / "articles"
for f in sorted(src.glob("[0-9][0-9]-*.md")):
    rec = build_record(f)
    if not is_publicly_published(rec):                # 검증 통과한 공개 글만 포함
        print(f"⏭️  미게시/URL 미검증 제외: {rec['id']}")
        continue
    records.append(rec)
    shutil.copyfile(f, articles_dir / f.name)
index = {"source": "blogs", "count": len(records), "articles": records}
(OUT_DIR / "articles_index.json").write_text(
    json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
```

두 가지를 강조합니다. 첫째, 이 스크립트는 **수동 선행 단계**입니다. 빌드 도구(예: Hatchling)에 자동 훅으로 연결하지 않으면, 스냅샷을 갱신하지 않은 채 패키징할 때 **오래된 데이터가 그대로 들어갑니다.** 그러니 "패키징 전에 빌드 스크립트를 실행"을 규칙으로 삼거나, 빌드 훅·CI 검증으로 생성물을 자동 갱신하십시오. 둘째, **패키지에는 공개된 글만** 담기도록 위 `is_publicly_published` 같은 술어로 미게시 원고를 걸러야 합니다. 다만 이 필터는 **현재 저장소의 `build_index.py`에는 아직 없어**, 지금 번들에는 홈 폴백된 2편이 들어 있습니다(공개 배포 전 반드시 추가). 원본 마크다운을 통째로 복사하면 초안 헤더·비공개 원고가 휠 안으로 딸려 들어갑니다. (빌드가 출력 `articles/`의 기존 마크다운을 먼저 비우는 정리 단계는 유지해야, 이전에 포함됐던 미게시 파일이 남지 않습니다.) 공개 배포 직전에는 **휠 자체를 금지 식별자·내부 경로 대상으로 한 번 더 스캔**하는 것을 권합니다.

패키징에서 데이터가 **패키지 하위 디렉터리**(`src/<pkg>/data/`)에 있으면 별도 매니페스트 없이 휠(wheel)에 자동 포함됩니다. 처음에는 빌드 백엔드에 `force-include`로 데이터를 중복 지정했다가 빌드가 깨졌는데, **패키지 하위 data는 자동 포함**이라 그 지정을 제거하니 해결됐습니다. 결과적으로 **콘텐츠 스냅샷이 self-contained**가 되어, 설치 후 원본 저장소나 콘텐츠 네트워크 호출 없이 동작합니다(단 `fastmcp` 같은 런타임 의존성은 설치 시 함께 받아야 하므로, 휠 파일 하나만으로 완결되는 것은 아닙니다).

## 7. 출처 링크 — 인용 가능성을 높이는 지점(강제는 아니다)

이 서버의 특징이 응축된 곳이 `get_article`의 **렌더링**입니다. 본문만 던지는 대신, 상단과 하단을 **원문 URL로 감쌉니다.**

```python
# 현재 로컬 구현(축약)
def render_article(self, article_id) -> str:
    rec = self._by_id.get(self._norm_id(article_id))
    if not rec:
        return f"글을 찾을 수 없습니다: {article_id!r}. search_articles로 id를 확인하세요."
    header = (
        f"# {rec['title']}\n\n"
        f"> 원문(정식 게시글): {rec['url']}\n"
        f"> 분류: {rec['category']}\n\n---\n\n"
    )
    footer = f"\n\n---\n원문 및 다른 글: {rec['url']}\n블로그: {BLOG_HOME}\n"
    return header + self._body(rec) + footer
```

여기에 두 겹의 유도가 있습니다. 데이터 겹으로는 본문을 열 때 원문 URL이 머리·꼬리에 실리고, 프롬프트 겹으로는 서버 `instructions`가 "인용 시 URL을 표기하라"고 안내합니다. 그 결과 사용자에게 보이는 답변에 원문 링크가 함께 남을 **가능성**이 커집니다.

다만 한계를 분명히 해야 합니다. **이것은 인용을 강제하지 못합니다.** MCP 도구 결과와 `instructions`는 모델·클라이언트에 제공되는 입력·힌트일 뿐, 최종 답변의 표기 방식을 통제하지 않습니다. 또 이렇게 남는 링크는 **에이전트 답변 안의 출처 링크(추천 유입)** 이지, 웹에서 크롤링되는 SEO 백링크와는 다릅니다. 범위도 정확히 해야 합니다 — URL은 **목록·검색 결과, 정상 본문 응답, 그리고 `blog_home`**에 실리며, `list_categories()`나 "글 없음" 오류 응답에는 URL이 없습니다. 또 앞서 말한 홈 폴백 글(현재 번들의 2편)은 정상 본문 응답이라도 개별 원문이 아니라 **홈 URL**이 실린다는 예외가 있습니다. `article_id`를 `"09"`·`"9"`·`"BLOG-09"` 어느 형태로 넣어도 받아 주도록 정규화해, 에이전트가 검색 결과의 id를 그대로 넘기다 실패하는 일은 줄였습니다.

## 8. 로컬 stdio로 먼저, 공개 배포는 다음

배포는 **로컬 표준입출력(stdio)부터** 시작하는 것이 가장 빠릅니다. 로컬 소스에서 서버를 띄워 내 AI 클라이언트에 한 줄로 붙이면 됩니다. 등록 형태(설정 파일 한 줄 또는 JSON)는 클라이언트마다 다르지만, 실행기로 로컬 패키지를 stdio로 실행한다는 점은 같습니다.

```jsonc
// 클라이언트 MCP 설정(예시) — 로컬 소스를 stdio로 실행
{
  "mcpServers": {
    "aiarchitect-blog": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/aiarchitect-blog-mcp",
               "aiarchitect-blog-mcp"]
    }
  }
}
```

읽기 전용·공개 데이터라서 **로컬 stdio에서는 인증이 필요 없습니다.** 서버 프로세스가 곧 내 머신이고, 다루는 것도 공개를 전제로 한 글이기 때문입니다(단 현재 로컬 번들에는 홈 폴백된 2편이 섞여 있어, 공개 배포 빌드에서는 6절처럼 제외해야 합니다). 다음 단계인 **원격 HTTP 공개 배포**로 넘어가면 이야기가 달라집니다.

- 공개 읽기 전용이라 **익명 접근을 허용**할 수도 있지만, 그때는 **속도 제한(Rate Limit)·쿼터·최대 응답 크기**를 기본 보호책으로 두어야 합니다(캐싱은 규모·호스팅에 따른 선택).
- 사용자·팀 단위로 붙이려면 표준 인증을 얹습니다. 최신 MCP는 인증 보호 서버에 대해 **RFC 9728 보호 리소스 메타데이터**와 인가 서버 메타데이터 디스커버리를 요구합니다. 그 표준 흐름은 [MCP OAuth 2.1 인증 구조](https://aiarchitect.tistory.com/11)에서, 여러 클라이언트 등록은 [원격 MCP 서버를 여러 클라이언트에 붙이기](https://aiarchitect.tistory.com/48)에서 다뤘습니다.
- 패키지 공개 배포(공개 저장소·패키지 레지스트리)로 넘어가면 실행기로 설치 없이 바로 띄우는 경험을 줄 수 있습니다. 이때 패키지 메타데이터(저장소 URL·작성자)에 **개인 식별자가 새지 않도록** 필명·조직 계정으로 정리해야 합니다. 이 단계는 별도 승인 후 진행할 계획입니다.

## 9. 읽기 전용이라도 신뢰 경계는 있다

"공개 데이터를 읽기만 하는데 보안이 왜 필요하냐"고 생각하기 쉽지만, 서버인 이상 최소한의 경계는 필요합니다.

- **입력 검증** — `article_id`·`query`·`limit`·`offset`은 신뢰하지 않는 입력입니다. 타입만 검증하면 함정이 있습니다. 예를 들어 `limit`이 정수라는 것만 보장하면 **음수 `limit`이 그대로 통과**해 의도치 않은 양의 결과가 나올 수 있습니다. `Annotated[int, Field(ge=1, le=50)]`로 범위를, `offset >= 0`을, 그리고 `query` 길이·토큰 수 상한을 명시해야 합니다. FastMCP가 함수 시그니처에서 검증 스키마를 만들어 주므로, 제약은 타입 힌트에 붙이면 됩니다.
- **읽기 전용 힌트** — 도구에 `readOnlyHint=True`(그리고 정적 번들이니 `openWorldHint=False`) 애너테이션을 선언하면, "이 서버는 읽기 전용"이라는 성질이 클라이언트에 기계적으로 전달됩니다. 기본값은 읽기 전용이 아니므로 명시하는 편이 좋습니다(단, 이는 보안 강제가 아니라 힌트입니다).
- **응답 크기** — `get_article`이 항상 전체 본문을 반환하면, 수만 자짜리 글에서는 로컬 stdio에서도 모델 컨텍스트를 크게 소비합니다. 목차·섹션 단위 조회나 `offset/max_chars` 페이지네이션을 두거나, 최소한 본문 최대 크기를 문서화하십시오. 원격이라면 응답 크기 상한도 함께 둡니다.
- **콘텐츠는 신뢰 경계 밖** — 본문에 삽입된 문구가 에이전트에게 지시처럼 읽힐 수 있습니다. 서버가 돌려주는 본문은 **데이터이지 명령이 아님**을 클라이언트 쪽에서 전제해야 합니다([Prompt Injection 방어](https://aiarchitect.tistory.com/23)). 읽기 전용 MCP 서버의 배포 점검 항목은 [MCP Server 보안 체크리스트](https://aiarchitect.tistory.com/22)에 정리돼 있습니다.

읽기 전용·공개 데이터라는 특성이 이 목록을 **짧게** 만들어 줄 뿐, 0으로 만들지는 않습니다.

## 10. 테스트 — 결정성을 활용하되 과신하지 않기

검색이 결정적이라는 성질은 곧 **테스트하기 쉽다**는 뜻입니다. 그래서 "질의 X → 상위에 글 Y", "본문 응답에 원문 URL이 머리·꼬리로 들어간다", "미게시 글은 제외/폴백된다" 같은 계약을 골든 테스트로 고정할 수 있습니다. 다만 **초안의 테스트가 실제보다 강하면 안 됩니다.** 지금 저장소의 기본 테스트는 결과가 비어 있지 않은지, URL·스니펫이 있는지 정도를 확인하는 수준이므로, 아래처럼 **순위와 백링크 위치를 명시적으로 고정하도록 강화**하는 것을 계획하고 있습니다.

```python
# 순위·백링크 테스트는 현재 corpus API로 바로 작성 가능(현재 구현).
def test_search_ranks_relevant_article_first():
    hits = corpus.search("MCP OAuth PKCE", limit=3)
    assert [h["id"] for h in hits[:1]] == ["09"]        # 순위를 명시적으로 고정

def test_article_wraps_body_with_backlink():
    lines = corpus.render_article("09").splitlines()
    assert lines[0].startswith("# ")
    assert "tistory.com/11" in lines[2]                 # 머리(원문 줄)에 그 글의 정확한 URL
    assert "tistory.com/11" in lines[-2]                # 꼬리에도 — '위치'까지 검증

# 제외 테스트는 목표 계약. 빌드 로직을 순수 함수 generate_index(src)로 분리한 뒤
# 실제 fixture로 검증한다(현재 스크립트는 main(src)만 있어 그대로는 실행 불가).
def test_unpublished_article_is_excluded():
    # fixture = 공개 글 2편(03·09) + 미게시 후보 1편(45)
    ids = {r["id"] for r in generate_index(FIXTURE_WITH_PUBLIC_AND_UNPUBLISHED)}
    assert "45" not in ids            # 미게시는 빠지고
    assert {"03", "09"} <= ids        # 공개 글은 남는다(공집합 통과 방지)
```

여기에 더해, 실제 MCP 클라이언트를 인메모리로 붙여 도구 호출까지 확인하는 **스모크 테스트**를 CI에 남겨 둘 만합니다. 다만 프로토콜 왕복이 통과한다고 해서, 자연어 지시에서 올바른 도구가 선택되는지나 최종 답변에 URL이 인용되는지까지 보장되는 것은 아닙니다 — 그 계층은 별도로 검증해야 합니다([자연어에서 MCP Tool Call까지: 통합 테스트](https://aiarchitect.tistory.com/14)). 결정적 산출물을 골든으로 묶는 방법은 [생성기 골든 테스트](https://aiarchitect.tistory.com/49)에서 더 다뤘습니다.

## 11. 체크리스트와 마무리

```text
[현재 완료 — 로컬 검증]
[x] 읽기 전용 최소 도구 집합(분류·목록·검색·본문·홈)
[x] instructions에 사용 순서·인용 안내
[x] 결정적 검색(같은 질의 → 같은 순서, 동점 규칙 명시)
[x] 콘텐츠 스냅샷을 패키지에 번들(원본 저장소 없이 동작)
[x] 정상 본문 응답 머리·꼬리에 원문 URL

[공개 배포 게이트 — 미반영, 배포 전 필수]
[ ] 미게시 원고 fail-closed 제외(홈 폴백을 인덱싱하지 않기)
[ ] limit·offset·query 범위·길이 검증(음수 limit 등)
[ ] readOnlyHint / openWorldHint 애너테이션 선언
[ ] 인덱스 생성 build hook/CI 자동화(오래된 데이터 방지)
[ ] get_article 응답 크기·페이지네이션 또는 최대 크기 문서화
[ ] 헤더 경계를 구분자/프론트매터로 확정·필수 필드/중복 ID 검증
[ ] 패키지 메타데이터·문서·이력에서 개인 식별자 제거
[ ] 코드 라이선스(MIT)와 콘텐츠 이용 조건(별도)을 구분해 명시
```

정리하면, 공개 콘텐츠를 MCP 서버로 만드는 일은 **거창한 인프라가 아니라 작은 읽기 전용 서버 하나**로 시작할 수 있습니다. 도구 표면을 좁게 유지하고, 헤더의 현실적 다양성을 파서로 흡수하고, 검색을 결정적으로 만들고, 응답에 원문 URL을 실어 **인용 가능성을 높이는 것** — 이 네 가지가 골격입니다. 다만 로컬 검증에서 공개 배포로 넘어갈 때는 **미게시 원고 제외·입력 검증·개인 식별자 정리** 같은 안전장치가 선행돼야 합니다. 그 경계만 지키면, 내 콘텐츠가 곧 나의 노출 채널이 됩니다.

함께 읽으면 좋은 글: [MCP란 무엇인가](https://aiarchitect.tistory.com/2), [MCP Tool 설계 원칙](https://aiarchitect.tistory.com/3), [MCP OAuth 2.1 인증 구조](https://aiarchitect.tistory.com/11), [원격 MCP 서버를 여러 클라이언트에 붙이기](https://aiarchitect.tistory.com/48), [MCP Server 보안 체크리스트](https://aiarchitect.tistory.com/22), [생성기 골든 테스트](https://aiarchitect.tistory.com/49).
