# 블로그 MCP 서버 공개 배포기: PyPI 패키징·하드닝·익명성 게이트

앞선 글 [내 블로그를 MCP 서버로 만들기](https://aiarchitect.tistory.com/63)에서는 이 블로그의 공개 글 코퍼스를 **로컬 stdio MCP 서버**로 만들어 AI 에이전트가 목록·검색·본문을 읽게 하는 데까지 다뤘다. 그 글은 마지막에 "로컬 stdio로 먼저, 공개 배포는 다음"이라고 미뤄 두었다. 이 글은 바로 그 **다음** 이야기다.

로컬에서 도는 것과 남들이 `uvx <패키지명>` 한 줄로 설치해 쓰는 것 사이에는 생각보다 큰 간극이 있다. 특히 **PyPI에 올린 배포 파일은 되돌리기 어렵다** — 이미 올린 wheel/sdist는 같은 파일명으로 교체할 수 없고, 수정본은 통상 새 버전 번호를 필요로 한다. 한 번 나간 아티팩트는 캐시·미러·포크에도 남는다. 그래서 배포는 "동작하니까 올린다"가 아니라 **배포 전에 굳혀도 되는 상태인지 검증하는 게이트**를 세우는 작업에 가깝다.

이 글에서 다루는 것: ① 데이터까지 담아 self-contained로 만드는 패키징, ② 되돌릴 수 없는 배포 전에 세운 하드닝 세 가지, ③ 단순 "금지어 스캔"이 놓치는 노출 면적과 그것을 다회 LLM 검토로 걸러낸 과정, ④ 디렉터리 등록으로 닫는 유입 루프.

## 1. 로컬 stdio에서 배포 가능한 패키지로

로컬 서버는 소스 디렉터리 안에서 데이터 파일을 상대 경로로 읽어도 된다. 하지만 배포본은 **설치된 site-packages 안에서 소스 저장소 없이도 동작**해야 한다. 핵심은 콘텐츠(글 본문 마크다운 + 인덱스)를 패키지 하위에 넣어 함께 배포하는 것이다.

`pyproject.toml`(hatchling 기준)에서 패키지 디렉터리를 지정하면, 그 하위의 `data/`는 기본적으로 함께 포함된다.

```toml
[project]
name = "aiarchitect-blog-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["fastmcp>=2.8,<4"]   # 상한(<4)으로 비호환 major 자동 선택 차단

[project.scripts]
aiarchitect-blog-mcp = "aiarchitect_blog_mcp:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aiarchitect_blog_mcp"]
# data/(인덱스 + 본문 *.md)는 패키지 하위라 기본 포함
```

의존성에 **상한**을 둔 점에 주목하자. `fastmcp>=2.8`처럼 하한만 두면, 나중에 호환이 깨지는 major 버전이 나왔을 때 예전에 배포한 `0.1.0`이 그 버전을 자동으로 끌어와 설치가 깨질 수 있다. 이 서버는 잠금파일(uv.lock)의 FastMCP 3.x에서 검증했고, `<4`는 2.8~4 전체를 검증했다는 뜻이 아니라 **아직 검증하지 않은 차기 major가 자동 유입되는 것을 막는 방어선**이다.

빌드는 `uv build`(또는 `python -m build`)로 wheel과 sdist를 만들고, **격리 환경에서 wheel만 설치해** 소스 없이 동작하는지 확인한다.

```bash
uv build                 # dist/*.whl, *.tar.gz
uv venv /tmp/smoke && uv pip install --python /tmp/smoke/bin/python dist/*.whl
# /tmp에서(소스 경로 밖에서) 실제 검색이 되는지 확인 → self-contained 확인
```

## 2. 되돌릴 수 없는 배포라는 전제

PyPI에 `0.1.0`을 올리면 그 릴리스의 파일은 **같은 파일명으로 교체할 수 없다**. 메타데이터 오타 하나, 번들에 딸려 들어간 파일 하나를 고치려면 통상 새 버전을 올려야 한다. yank는 가능하지만 비파괴적이라 정확한 버전을 고정한 설치에는 여전히 선택될 수 있고, 이미 받아 간 사람·캐시·미러에는 소용이 없다.

그래서 배포 직전 체크리스트는 "기능이 되는가"보다 **"이 상태로 영구히 남아도 괜찮은가"**를 묻는다.

- 서빙 로직이 의도치 않은 데이터를 노출하지 않는가(하드닝)
- 잘못된 입력에 서버가 죽지 않는가(입력 검증)
- 아티팩트 안에 있으면 곤란한 것이 없는가(노출 면적)
- 라이선스·메타데이터가 정확한가

아래 3~7절이 이 질문들에 대한 답이다.

## 3. 하드닝 ① 서빙은 기본 거부(fail-closed)로

이 서버는 각 글의 "원문(정식 게시글) URL"을 응답에 실어 준다. 그런데 아직 URL이 발급되지 않은 글은 블로그 홈으로 폴백될 수 있다. 홈 폴백 URL을 그대로 노출하면 **출처가 엉뚱한 곳을 가리키는** 오도성 응답이 된다.

해결은 "정식 게시글 URL을 가진 글만 서빙"하는 **기본 거부** 원칙이다. 먼저 "정식 게시글 URL"을 엄격히 판정한다.

```python
import re

# 개별 게시글 URL만 허용. 글 번호는 ASCII 양의 정수만(0·앞자리 0·유니코드 숫자 거부).
_ARTICLE_URL = re.compile(r"^https://aiarchitect\.tistory\.com/[1-9][0-9]*/?$")

def is_published(url: str) -> bool:
    if not isinstance(url, str):
        return False
    return bool(_ARTICLE_URL.match(url.strip()))
```

정규식에서 `\d` 대신 **`[0-9]`**를 쓴 이유가 있다. 파이썬 `re`의 `\d`는 유니코드 숫자(전각 `２`, 아랍-인도 `٢` 등)까지 매칭한다. `\d*`로 두면 `/1２` 같은 값이 통과해 버린다. 실제 검토에서 이걸 지적받고 `[1-9][0-9]*`로 좁혔다.

그리고 목록·검색·본문 어디서도 미게시 글이 새지 않도록, 레코드 판정을 **URL 정식성과 플래그를 둘 다** 요구하도록 만들었다.

```python
@staticmethod
def _is_published_rec(rec: dict) -> bool:
    # URL이 정식 게시글이어야 하고(홈 URL·외부 도메인 거부),
    # published 플래그가 '명시'돼 있으면 엄격히 True여야 한다.
    # 단, 플래그가 아예 없는 레코드는 구 인덱스 호환을 위해 URL 판정으로 폴백한다.
    return is_published(rec.get("url", "")) and rec.get("published", True) is True
```

`bool(rec["published"])`로만 판정하면 문자열 `"false"`(참값)나 홈 URL+`True` 조합이 통과한다. `is True`로 엄격히 비교하고 URL 검증을 **AND**로 묶어, 홈 URL·외부 도메인·`"false"` 같은 명시적 우회 조합을 막았다.

한 가지 정직하게 짚을 점이 있다. 위 코드는 `rec.get("published", True)`라서 **`published` 키가 아예 없는 레코드는 URL 정식성 판정으로 폴백**한다(플래그가 없던 이전 인덱스와의 호환). 즉 "정식 URL이면서, 명시된 플래그가 비-True가 아닐 것"이다. 더 엄격하게 하려면 기본값을 `False`로 두어 플래그 누락 자체를 거부하면 된다 — 다만 그건 인덱스 스키마를 함께 바꾸는 다음 버전의 일이다. 이처럼 "어디까지가 기본 거부이고 어디부터가 호환 폴백인지"를 정확히 아는 것이 하드닝의 절반이다.

## 4. 하드닝 ② 입력은 클램프하고, 예외는 삼킨다

읽기 전용 서버라도 도구 인자는 외부(에이전트)에서 온다. `limit`에 음수·거대값·엉뚱한 타입이 들어와도 서버가 죽으면 안 된다. 상·하한으로 클램프하되, 변환 불가 값은 기본값으로 되돌린다.

```python
def _clamp_int(value, default: int, lo: int, hi: int) -> int:
    if isinstance(value, bool):          # bool은 int의 하위형 → 오입력 방어
        return default
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default                   # inf/NaN(OverflowError·ValueError)도 방어
    return max(lo, min(n, hi))
```

여기서 `OverflowError`를 빠뜨리기 쉽다. `int(float("inf"))`는 `OverflowError`를 던진다. `TypeError, ValueError`만 잡으면 `limit=inf` 한 방에 도구 호출이 실패한다. 경계 입력(무한대·NaN·bool·음수·거대값)은 **회귀 테스트로 고정**해 둔다.

## 5. 하드닝 ③ 읽기 전용임을 프로토콜에 선언한다

MCP 도구는 애노테이션으로 "이 도구가 무엇을 하는지"를 힌트로 줄 수 있다. 이 서버의 5개 도구는 전부 읽기 전용·부작용 없음·외부 세계를 건드리지 않음이다. 이를 명시하면 클라이언트가 승인·표시 정책을 더 안전하게 잡는다.

```python
@mcp.tool(annotations={
    "readOnlyHint": True,      # 환경 상태를 바꾸지 않음
    "idempotentHint": True,    # 같은 인자로 반복 호출해도 추가 효과 없음
    "openWorldHint": False,    # 상호작용 영역이 닫혀 있음(개방형 외부 시스템과 상호작용하지 않음)
})
def search_articles(query: str, limit: int = 10) -> list[dict]:
    ...
```

이 애노테이션은 서버가 스스로 선언하는 **비강제적 힌트**다([ToolAnnotations 사양](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations)). 실제 권한·부작용 통제를 대신하지 않으며, 클라이언트도 신뢰할 수 없는 서버의 힌트를 보안 결정에 그대로 쓰면 안 된다. 그렇더라도 **실제 동작과 어긋나게 달면 안 된다** — 읽기 전용이 아닌 도구에 `readOnlyHint`를 달면 잘못된 신호를 준다. 배포본에서 5개 도구가 실제로 이 값을 노출하는지 in-memory 클라이언트로 확인했다.

## 6. "금지어 스캔"이 놓치는 것 — 배포 아티팩트의 노출 면적

여기서부터가 이 글에서 가장 하고 싶은 이야기다. 익명으로 운영하는 프로젝트를 공개 배포할 때, 흔히 "실명·회사명·이메일 같은 금지 식별자를 grep으로 스캔"한다. 그건 필요조건일 뿐 충분하지 않다. 스캔은 깨끗한데도 배포 아티팩트가 다음을 흘릴 수 있다.

**(a) 번들 데이터에 딸려 온 편집용 메타.** 이 서버의 본문 마크다운은 원래 상단에 작성용 헤더 블록(초안 상태·권장 제목·내부 이미지 경로 같은 편집 파이프라인 메타)을 갖고 있었다. 런타임에서는 본문 추출기가 이 헤더를 떼고 서빙하지만, **원본 `.md` 파일 자체는 wheel·sdist에 그대로 들어가** 누구나 `pip download` 후 열어볼 수 있었다. 서빙이 깨끗한 것과 아티팩트가 깨끗한 것은 다르다.

해결은 빌드 단계에서 번들에 **본문만** 넣는 것이다. 서빙과 같은 추출기를 재사용해, 공개 H1부터 시작하는 깨끗한 파일을 쓴다.

```python
# 빌드 시: 통짜 복사 대신, 편집 헤더를 떼고 공개 본문만 번들에 저장
body = extract_body(src.read_text(encoding="utf-8")).rstrip() + "\n"
(out_dir / src.name).write_text(body, encoding="utf-8")
```

**(b) 소스·메타데이터에 박힌 내부 경로.** 빌드 스크립트의 기본 소스 경로, README의 예시 명령, 인덱스의 `source` 필드에 내부 작업 저장소 경로가 하드코딩돼 있었다. README는 wheel 메타데이터(`METADATA`)로도 복제되어 아티팩트에 노출된다. 내부 경로는 실명이 아니어도 **작업 환경 구조를 드러내는 식별자**다. 중립 경로(`/path/to/blogs`)와 공개 URL로 바꿨다.

**(c) git 이력과 삭제한 파일.** HEAD에서 지운 내부 체크리스트 파일이 과거 커밋에는 그대로 남아 clone 후 복원 가능했다. 아티팩트뿐 아니라 **공개 저장소의 이력**도 노출 면적이다.

**(d) sdist에 자동으로 딸려가는 파일.** 배포 표면을 줄이려고 넣은 테스트가 "무엇을 걸러내는지"를 리터럴로 담고 있어, sdist에 그 문자열이 실렸다. `include`로 테스트 같은 **일반 선택 파일**을 제외해 표면을 좁혔다.

```toml
[tool.hatch.build.targets.sdist]
# 소스·스크립트·문서·잠금파일만 선택 → 테스트 등 일반 파일은 제외
include = ["/src", "/scripts", "/README.md", "/LICENSE", "/pyproject.toml", "/uv.lock"]
```

주의: Hatch sdist는 `pyproject.toml`·README·LICENSE·`.gitignore`·`PKG-INFO` 같은 파일을 `include`와 무관하게 **항상 포함**한다. 그래서 `.gitignore`는 그대로 들어가며, 나는 `.gitignore`에서 내부 파일명 참조를 따로 걷어낸 뒤 **최종 tar 파일 목록을 직접 검사**했다. "include = 완전한 허용 목록"이 아니라는 점을 아는 게 중요하다.

**(e) 라이선스 범위.** 코드는 MIT지만 블로그 글 본문은 저작권이 원저자에게 있다. `pyproject`·`LICENSE`가 프로젝트 전체를 MIT로 표기하면 글까지 MIT처럼 읽힌다. LICENSE 상단에 "MIT는 소스 코드에 적용, 번들 글 본문은 별도"라는 범위 주석을 달아 **LICENSE·README에서 적용 범위를 명시**했다. 다만 wheel `METADATA`에는 여전히 `License: MIT`가 남아 있어, 혼합 라이선스를 메타데이터에서 어떻게 표현할지는 다음 버전의 숙제다.

## 7. 배포 전 검토 게이트 — 다회 LLM 리뷰로 P0를 거른다

위 (a)~(e)는 사람이 한 번 훑어서 다 잡기 어렵다. 그래서 **되돌릴 수 없는 배포 직전에 검토 게이트**를 세웠다. 코드·데이터·빌드 산출물을 읽을 수 있는 별도 LLM(리뷰어 역할)에게 명시적 기준으로 판정을 시켰다.

검토 축을 이렇게 나눴다.

- **개인정보/익명성**: 소스·번들 데이터·인덱스·wheel/sdist 메타·git 저자에 금지 식별자가 있는가
- **내부 프로세스 노출**: 편집 메타·내부 저장소 경로 등 아티팩트에 남는 프로세스 흔적
- **패키징 정합성**: 메타데이터·라이선스·self-contained·내부 파일 배제
- **하드닝 정확성**: fail-closed·입력 검증·애노테이션이 실제로 맞는가, 우회로는 없는가
- **되돌림 불가 리스크**: 버전을 올려야만 고칠 수 있는 요소

핵심은 **한 번으로 끝내지 않은 것**이다. 1차는 번들 데이터의 편집 메타를 P0로 지적했고, 그걸 고쳐 넣은 2차에서 **새로운 P0**(내부 저장소 경로가 README→wheel 메타데이터로 복제됨)를 또 잡았다. 유니코드 숫자 우회는 이때 P1로 함께 나왔다. 3차에서야 "게시 가능" 판정이 나왔다. 한 라운드로 끝냈다면 두 번째 P0는 그대로 배포됐을 것이다.

한 가지 정직하게 한정할 점이 있다. 이 판정의 **범위는 배포 아티팩트(wheel·sdist)와 그 메타데이터**였다. 공개 저장소의 git 이력(커밋 저자 이메일, 과거 커밋에 남은 삭제 파일)은 이미 공개된 이력을 재작성하는 파급이 크므로 이번 게이트에서 **의도적으로 분리**했다 — 아티팩트 하드닝과는 다른 축의 결정이다. 그래서 "게시 가능"은 "정의한 아티팩트 범위에서 차단 문제 0"이지 "공개 표면 전체가 완벽히 익명"이라는 뜻이 아니다. 소스 이력 위생은 별도로 다뤄야 한다.

> 교훈: 되돌릴 수 없는 공개에서 검토 게이트의 가치는 "한 번 훑기"가 아니라 **수정→재검토를 반복해 (정의한 범위의) 차단 문제가 0으로 수렴할 때까지 가는 것**이다. 그리고 그 범위가 어디까지인지 분명히 말하는 것도 정직성의 일부다.

배포 직전엔 기계적 검증도 함께 돌린다. `twine check`로 README(long description) 렌더링을 확인하고, 격리 설치로 self-contained를, 별도 메타데이터 파싱과 아티팩트 전수 grep으로 금지 식별자·내부 경로·편집 마커가 0인지 마지막으로 확인한다.

## 8. 배포와 태깅 — 아티팩트와 소스를 일치시킨다

게이트를 통과하면 배포한다. 이때 **배포하는 아티팩트가 어떤 커밋에서 나왔는지**를 고정하는 게 중요하다. 작업트리가 미커밋 상태에서 배포하면, 공개 저장소의 소스와 PyPI의 아티팩트가 어긋난다.

순서는: 정리 사항을 커밋 → 공개 저장소에 push → `v0.1.0` 태그 → 그 상태에서 재빌드 → 최종 스캔·`twine check` → 업로드. 토큰 같은 비밀은 환경 변수로 주입하고 로그·기록에 남기지 않는다.

```bash
# 예시 흐름(토큰은 환경변수로만)
git tag v0.1.0 && git push origin main --tags
uv build
export UV_PUBLISH_TOKEN="***"   # 붙여넣지 말고 안전 주입
uv publish
uvx aiarchitect-blog-mcp        # 실제 PyPI에서 설치·동작 확인
```

업로드 후엔 **실제 PyPI에서 새로 설치**해 도구 목록·검색·본문·애노테이션이 정상인지 확인한다. 로컬 빌드가 아니라 배포본을 검증하는 게 배포 성공의 기준이다.

## 9. 디렉터리 등록과 유입 루프

배포가 끝이 아니다. AI 에이전트·개발자가 서버를 **발견**해야 유입 루프가 돈다. MCP 서버 디렉터리(레지스트리)에 등록하면 검색·카테고리에서 노출된다. 상당수 디렉터리는 공개 GitHub 저장소를 자동 인덱싱하고, 일부는 저장소 루트에 작은 메타 파일을 두면 소유권을 주장할 수 있다.

```json
{ "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["<공개 핸들>"] }
```

여기서 **발견 → 원문 이동 경로**가 만들어진다. 블로그 글이 서버로 사람을 보내고(설치·사용), 서버 응답이 각 글의 **원문 URL**을 실어 블로그로 되돌리는 경로다(실제 유입량이 얼마나 되는지는 별개의 측정 문제다). 검색엔진·AI 에이전트 양쪽에 노출하는 이야기는 [이 글](https://aiarchitect.tistory.com/64)에서 더 다뤘다.

## 10. 배포 전 체크리스트

- [ ] wheel만 격리 설치해 **소스 없이** 목록·검색·본문 동작(self-contained)
- [ ] 서빙 fail-closed: 홈 폴백·미게시 글이 목록·검색·본문 어디에도 안 보임
- [ ] 입력 클램프: 음수·거대값·`inf`/`NaN`·bool·잘못된 타입에 안 죽음
- [ ] 도구 애노테이션(`readOnlyHint`/`idempotentHint`/`openWorldHint`)이 실제와 일치
- [ ] 번들 데이터에 편집 메타·내부 경로 0 (본문만 번들)
- [ ] 소스·README·메타데이터·인덱스에 내부 저장소 경로 0
- [ ] sdist 최종 tar 목록 직접 검사: `include`로 테스트 등 선택 파일 제외 + 항상 포함되는 `pyproject.toml`·README·LICENSE·`.gitignore`·`PKG-INFO`의 공개 적합성 확인
- [ ] 라이선스 범위 명시(코드=MIT / 콘텐츠=별도)
- [ ] git 이력에 실명·회사·삭제한 내부 파일 잔존 0
- [ ] `twine check` 통과, 아티팩트 전수 금지 식별자·내부 경로 스캔 0
- [ ] 커밋·태그 후 그 상태에서 재빌드 → 업로드, **실제 배포본**으로 재검증

## 11. 마무리

로컬에서 도는 MCP 서버를 공개 배포하는 일의 절반은 패키징이지만, 나머지 절반은 **"되돌릴 수 없다"는 전제 아래 무엇을 굳혀도 되는지 검증하는 것**이다. 특히 익명 프로젝트에서는 금지어 스캔만으로 부족하다 — 번들 데이터의 편집 메타, 메타데이터로 복제되는 내부 경로, git 이력, sdist 동봉 파일까지가 노출 면적이고, 이것들은 수정→재검토를 반복하는 게이트로 수렴시켜야 한다.

작게 시작해(읽기 전용·결정적) 로컬에서 검증하고, 배포 전에 하드닝과 검토 게이트를 세운 뒤, 디렉터리로 발견성을 얻어 발견→원문 이동 경로를 만든다. 이 순서가 콘텐츠를 AI 시대에 노출하는 안전한 경로다.

> 블로그·사내 지식 콘텐츠를 MCP나 RAG로 연결하는 구축을 검토하고 있다면, 공개 범위와 권한 경계부터 단계적으로 설계할 수 있습니다.
> [크몽에서 AI Agent·RAG·MCP 구축 상담하기](https://kmong.com/gig/798627)

### 참고자료

- Model Context Protocol — [ToolAnnotations 사양(2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations)
- Python Packaging — [Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- Hatch — [Build configuration](https://hatch.pypa.io/latest/config/build/)
- uv — [패키지 빌드·배포 가이드](https://docs.astral.sh/uv/guides/package/)
- PyPI — [파일명 재사용 정책](https://pypi.org/help/#file-name-reuse) · [yanking](https://docs.pypi.org/project-management/yanking/)
- Twine — [twine check](https://twine.readthedocs.io/en/stable/#twine-check)
