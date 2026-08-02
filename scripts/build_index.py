#!/usr/bin/env python3
"""공개 블로그 마크다운 코퍼스 → 번들 인덱스(articles_index.json) + 본문 스냅샷 생성.

기본 소스: ../github-portfolio-public/aiarchitect/blogs/*.md
산출물:    src/aiarchitect_blog_mcp/data/{articles_index.json, articles/*.md}

사용:
    python scripts/build_index.py [SOURCE_DIR]
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# 설치 없이 패키지 파서를 임포트할 수 있도록 src를 경로에 추가
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aiarchitect_blog_mcp.corpus import build_record  # noqa: E402

DEFAULT_SRC = _ROOT.parent / "github-portfolio-public" / "aiarchitect" / "blogs"
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

    articles_dir = OUT_DIR / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    for old in articles_dir.glob("*.md"):
        old.unlink()

    kept_files = {r["file"] for r in records}
    for f in files:
        if f.name in kept_files:
            shutil.copyfile(f, articles_dir / f.name)

    index = {"source": "aiarchitect/blogs", "count": len(records), "articles": records}
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
