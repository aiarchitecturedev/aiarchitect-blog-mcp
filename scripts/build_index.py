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
from pathlib import Path

# 설치 없이 패키지 파서를 임포트할 수 있도록 src를 경로에 추가
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aiarchitect_blog_mcp.corpus import (  # noqa: E402
    build_record,
    extract_body,
    is_published,
)

# 기본 소스는 저장소 루트의 blogs/(없으면 인자로 지정). 내부 저장소 경로를 하드코딩하지 않는다.
DEFAULT_SRC = _ROOT / "blogs"
OUT_DIR = _ROOT / "src" / "aiarchitect_blog_mcp" / "data"


def main(src: Path, include_unpublished: bool = False) -> int:
    if not src.exists():
        print(f"❌ 소스 디렉터리 없음: {src}", file=sys.stderr)
        return 1

    files = sorted(p for p in src.glob("[0-9][0-9]-*.md"))
    if not files:
        print(f"❌ 마크다운 글을 찾지 못함: {src}", file=sys.stderr)
        return 1

    all_records = [build_record(f) for f in files]

    # fail-closed: 정식 게시 URL이 없는(홈 폴백) 글은 공개 배포 번들에서 기본 제외한다.
    excluded = [r for r in all_records if not r["published"]]
    records = all_records if include_unpublished else [r for r in all_records if r["published"]]

    # 불변조건(fail-closed): 기존 산출물을 건드리기 전에 먼저 검사한다(검증 실패 시 데이터 보존).
    ids = [r["id"] for r in records]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        print(f"❌ 중복 id: {dups}", file=sys.stderr)
        return 1
    urls = [r["url"] for r in records]
    url_dups = sorted({u for u in urls if urls.count(u) > 1})
    if url_dups:
        print(f"❌ 중복 URL: {url_dups}", file=sys.stderr)
        return 1
    not_published = [r["id"] for r in records if not is_published(r["url"])]
    if not_published:
        print(f"❌ 정식 게시 URL 아님(서빙 불가): {not_published}", file=sys.stderr)
        return 1

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
            body = extract_body(f.read_text(encoding="utf-8")).rstrip() + "\n"
            (articles_dir / f.name).write_text(body, encoding="utf-8")

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
