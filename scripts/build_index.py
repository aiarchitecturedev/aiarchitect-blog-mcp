#!/usr/bin/env python3
"""공개 블로그 마크다운 코퍼스 → 번들 인덱스(articles_index.json) + 본문 스냅샷 생성.

소스:   인자로 지정한 블로그 마크다운 디렉터리(파일명 형식 `NN-*.md`).
산출물: src/aiarchitect_blog_mcp/data/{articles_index.json, articles/*.md}

사용:
    python scripts/build_index.py /path/to/blogs
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# 설치 없이 패키지 파서를 임포트할 수 있도록 src를 경로에 추가
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aiarchitect_blog_mcp.corpus import (  # noqa: E402
    build_record,
    extract_body,
    is_published,
    parse_metadata,
)

# 기본 소스는 저장소 루트의 blogs/(없으면 인자로 지정). 내부 저장소 경로를 하드코딩하지 않는다.
DEFAULT_SRC = _ROOT / "blogs"
OUT_DIR = _ROOT / "src" / "aiarchitect_blog_mcp" / "data"
EXPECTED_IDS = tuple(f"{number:02d}" for number in range(1, 70))
EXPECTED_CATEGORY_COUNTS = {
    "보안": 19,
    "엔터프라이즈 아키텍처": 14,
    "개발 도구 · 자동화": 11,
    "AI Agent · MCP": 8,
    "기술 인사이트": 6,
    "프로젝트 문제 해결": 6,
    "RAG · LLM 시스템": 5,
}
# 익명성 denylist는 비배포 로컬 파일(.private-tokens)에서 로드한다.
# 개인 식별자 리터럴을 소스·번들·배포물에 남기지 않기 위함(release #16).
PRIVATE_TOKENS_FILE = _ROOT / ".private-tokens"


def load_private_tokens(path: Path = PRIVATE_TOKENS_FILE) -> tuple[str, ...]:
    """비배포 로컬 파일에서 소문자 denylist 토큰을 로드. 없으면 빈 튜플."""
    if not path.exists():
        return ()
    tokens = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            tokens.append(s.lower())
    return tuple(tokens)


FORBIDDEN_PRIVATE_TOKENS = load_private_tokens()


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def main(src: Path, include_unpublished: bool = False) -> int:
    if not src.exists():
        print(f"❌ 소스 디렉터리 없음: {src}", file=sys.stderr)
        return 1

    files = sorted(p for p in src.glob("[0-9][0-9]-*.md"))
    if not files:
        print(f"❌ 마크다운 글을 찾지 못함: {src}", file=sys.stderr)
        return 1

    # 정확한 69편 소스가 준비되지 않은 상태에서 기존 번들을 지우는 일을 막는다.
    source_ids = [path.name[:2] for path in files]
    if source_ids != list(EXPECTED_IDS):
        missing = sorted(set(EXPECTED_IDS) - set(source_ids))
        unexpected = sorted(set(source_ids) - set(EXPECTED_IDS))
        duplicates = _duplicates(source_ids)
        print(
            "❌ 소스 ID 프리플라이트 실패: "
            f"count={len(files)}, missing={missing}, unexpected={unexpected}, duplicates={duplicates}",
            file=sys.stderr,
        )
        return 1

    all_records = [build_record(f) for f in files]

    record_ids = [record["id"] for record in all_records]
    if record_ids != list(EXPECTED_IDS):
        print(
            f"❌ 메타데이터 ID 프리플라이트 실패: expected={list(EXPECTED_IDS)}, actual={record_ids}",
            file=sys.stderr,
        )
        return 1

    # fail-closed: 정식 게시 URL이 없는(홈 폴백) 글은 공개 배포 번들에서 기본 제외한다.
    excluded = [r for r in all_records if not r["published"]]
    records = all_records if include_unpublished else [r for r in all_records if r["published"]]

    # 불변조건(fail-closed): 기존 산출물을 건드리기 전에 먼저 검사한다(검증 실패 시 데이터 보존).
    ids = [r["id"] for r in records]
    if ids != list(EXPECTED_IDS):
        print(
            f"❌ 공개 글 프리플라이트 실패: expected=69, actual={len(records)}, "
            f"excluded={[record['id'] for record in excluded]}",
            file=sys.stderr,
        )
        return 1
    dups = _duplicates(ids)
    if dups:
        print(f"❌ 중복 id: {dups}", file=sys.stderr)
        return 1
    urls = [r["url"] for r in records]
    url_dups = _duplicates(urls)
    if url_dups:
        print(f"❌ 중복 URL: {url_dups}", file=sys.stderr)
        return 1
    not_published = [r["id"] for r in records if not is_published(r["url"])]
    if not_published:
        print(f"❌ 정식 게시 URL 아님(서빙 불가): {not_published}", file=sys.stderr)
        return 1

    category_counts = Counter(record["category"] for record in records)
    if category_counts != Counter(EXPECTED_CATEGORY_COUNTS):
        print(
            f"❌ 분류 수 프리플라이트 실패: expected={EXPECTED_CATEGORY_COUNTS}, "
            f"actual={dict(category_counts)}",
            file=sys.stderr,
        )
        return 1

    if not FORBIDDEN_PRIVATE_TOKENS:
        print(
            "⚠️ 익명성 denylist(.private-tokens) 미로드 — 정확 토큰 검사 생략. "
            "유지관리자는 비배포 로컬 정책 파일을 준비하세요.",
            file=sys.stderr,
        )

    bodies: dict[str, str] = {}
    for path in files:
        body = extract_body(path.read_text(encoding="utf-8")).rstrip() + "\n"
        if not body.startswith("# ") or parse_metadata(body):
            print(f"❌ 정제 본문 프리플라이트 실패: {path.name}", file=sys.stderr)
            return 1
        lowered = body.lower()
        leaked = [token for token in FORBIDDEN_PRIVATE_TOKENS if token in lowered]
        if leaked:
            print(f"❌ 비공개 식별자 프리플라이트 실패: {path.name}: {leaked}", file=sys.stderr)
            return 1
        bodies[path.name] = body

    # 검사를 통과한 뒤에만 기존 산출물을 교체한다.
    articles_dir = OUT_DIR / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    for old in articles_dir.glob("*.md"):
        old.unlink()

    kept_files = {r["file"] for r in records}
    for f in files:
        if f.name in kept_files:
            # 내부 편집 헤더(상태·승인·권장*·내부 경로·도식 정책 등)를 제거하고
            # 공개 본문(실제 H1부터)만 번들에 저장한다. 서빙과 동일한 extract_body 사용.
            (articles_dir / f.name).write_text(bodies[f.name], encoding="utf-8")

    index = {"source": "https://aiarchitect.tistory.com/", "count": len(records), "articles": records}
    (OUT_DIR / "articles_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cats = sorted({r["category"] for r in records})
    print(f"✅ {len(records)}편 인덱싱 완료 → {OUT_DIR / 'articles_index.json'}")
    print(f"   분류 {len(cats)}종: {', '.join(cats)}")
    if excluded:
        ids = ", ".join(r["id"] for r in excluded)
        if include_unpublished:
            print(f"   ⚠️ 정식 게시 URL 없음(홈 폴백) {len(excluded)}편 포함됨(--include-unpublished): {ids}")
            print("      → 공개 배포용 번들에는 이 글들을 넣지 마세요(홈 폴백 = 오도성 출처 링크).")
        else:
            print(f"   🔒 fail-closed 제외 {len(excluded)}편(정식 게시 URL 없음): {ids}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    include_unpublished = "--include-unpublished" in args
    args = [a for a in args if not a.startswith("--")]
    source = Path(args[0]).resolve() if args else DEFAULT_SRC
    raise SystemExit(main(source, include_unpublished=include_unpublished))
