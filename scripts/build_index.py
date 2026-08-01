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


def main(src: Path) -> int:
    if not src.exists():
        print(f"❌ 소스 디렉터리 없음: {src}", file=sys.stderr)
        return 1

    files = sorted(p for p in src.glob("[0-9][0-9]-*.md"))
    if not files:
        print(f"❌ 마크다운 글을 찾지 못함: {src}", file=sys.stderr)
        return 1

    articles_dir = OUT_DIR / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    for old in articles_dir.glob("*.md"):
        old.unlink()

    records = []
    for f in files:
        records.append(build_record(f))
        shutil.copyfile(f, articles_dir / f.name)

    index = {"source": "aiarchitect/blogs", "count": len(records), "articles": records}
    (OUT_DIR / "articles_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cats = sorted({r["category"] for r in records})
    print(f"✅ {len(records)}편 인덱싱 완료 → {OUT_DIR / 'articles_index.json'}")
    print(f"   분류 {len(cats)}종: {', '.join(cats)}")
    missing_url = [r["id"] for r in records if not r["url"].startswith("https://aiarchitect.tistory.com/") or r["url"].rstrip("/") == "https://aiarchitect.tistory.com"]
    if missing_url:
        print(f"   ⚠️ 정식 게시 URL 미발급(홈 폴백): {', '.join(missing_url)}")
    return 0


if __name__ == "__main__":
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SRC
    raise SystemExit(main(source))
