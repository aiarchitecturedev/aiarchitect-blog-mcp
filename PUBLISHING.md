# 📦 배포 체크리스트 (Boss 승인 후 실행)

> ⚠️ 아래는 **외부 공개 행위**입니다. Boss의 명시적 승인 후에만 진행합니다.
> 익명성 원칙: 공개 페르소나 **AI아키텍트 / aiarchitect.tistory.com** 만 사용.

## 0. 사전 점검 (로컬, 승인 불필요) — ✅ 완료

- [x] `uv run pytest -q` — **14/14 통과**(하드닝 케이스 포함)
- [x] 인메모리 MCP 스모크 — 도구 5종·검색 랭킹(09·22·47)·백링크
- [x] 실제 stdio 서브프로세스 end-to-end
- [x] `uv build` — sdist + wheel, **49편 데이터 번들 확인**
- [x] 격리 환경 wheel 설치 실행 — self-contained(소스 없이 49편·검색·본문)
- [x] 금지 식별자 스캔 클린 (source·dist·번들 md 전부; Keycloak은 공개 OSS 오탐)
- [x] `claude mcp add` 로컬 등록 — Connected
- [x] **하드닝(task#15)**: fail-closed(정식 게시 URL 없는 글 서빙 제외)·입력 검증
      (`limit`/`offset` 클램프·타입 방어)·`readOnlyHint` 5종·BLOG-02/45 실 URL 보정
- [x] 배포 직전 재빌드 + 금지토큰 재스캔 (2026-08-02 수행) — 콘텐츠 갱신 시 반복

## 1. PyPI 게시

필요: PyPI 계정 + API 토큰(Boss 제공). 익명 유지 위해 **전용 이메일**로 가입 권장.

```bash
cd aiarchitect-blog-mcp
python scripts/build_index.py        # 최신 블로그 반영
uv build                             # dist/*.whl, *.tar.gz
uv publish --token pypi-XXXX         # 또는 twine upload dist/*
```

- 게시 전 `dist/` 내 파일에 금지 식별자 없는지 재확인.
- 첫 게시 후 `uvx aiarchitect-blog-mcp` 로 실제 설치·동작 확인.

## 2. 공개 GitHub 저장소

- 신규 public repo 권장(예: `<필명-또는-조직>/aiarchitect-blog-mcp`; 개인 실명 핸들 금지).
- `pyproject.toml`의 `Source` URL을 실제 repo로 맞춤.
- `data/articles/*.md`, `articles_index.json` 커밋 포함(빌드 산출물이지만 self-contained 배포용).
- 커밋에 실명·회사·내부 정보 금지. 커밋 저자도 공개 페르소나로.

## 3. 발견성(선택) — MCP 디렉터리 등록

- glama.ai / mcp.so / `punkpeye/awesome-mcp-servers` 등에 제출.
- README에 설치 원클릭·데모 GIF 추가 시 채택률 ↑.

## 4. 홍보 루프

- 블로그에 **BLOG-61 "내 블로그를 MCP 서버로 만들기"** 게시 → repo/PyPI 링크.
- 이 글이 서버로 역유입되고, 서버 응답이 블로그로 역유입되는 순환 구조.

## ❓ Boss에게 필요한 결정/자원

1. PyPI 계정·API 토큰 (또는 신규 가입).
2. 공개 repo 이름·소유 계정 확정.
3. 패키지명 `aiarchitect-blog-mcp` 확정(PyPI 중복 시 대체명).
