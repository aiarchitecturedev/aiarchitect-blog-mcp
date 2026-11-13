#!/usr/bin/env python3
"""빌드 산출물(wheel·sdist) 배포 전 검증.

`uv build`가 만든 아티팩트가 **자기 완결적인지** 확인한다. 서빙 코드가 멀쩡해도
데이터 번들이 빠진 wheel은 설치한 쪽에서만 깨지므로, 소스 트리가 아니라
**아티팩트 안쪽**을 본다.

검사 항목(PUBLISHING.md의 수동 배포 체크리스트와 1:1):
  1. wheel·sdist에 본문 마크다운과 인덱스가 들어 있고 편수가 서로 맞는다
  2. 인덱스의 `count` ↔ 레코드 수 ↔ 번들 파일 집합이 일치한다
  3. 서빙되는 글은 전부 정식 게시 URL을 가진다(fail-closed)

격리 환경에 wheel만 설치해 실제로 동작하는지는 `--installed`로 검사한다
(설치된 패키지를 임포트하므로, 소스 트리 밖에서 실행해야 의미가 있다).

사용:
    python scripts/verify_dist.py dist/          # 아티팩트 내용물 검사
    python scripts/verify_dist.py --installed    # 설치본 동작 검사
"""

from __future__ import annotations

import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ARTICLE_MD = re.compile(r"(?:^|/)data/articles/[^/]+\.md$")
INDEX_JSON = re.compile(r"(?:^|/)data/articles_index\.json$")


def _fail(message: str) -> int:
    print(f"❌ {message}", file=sys.stderr)
    return 1


def _check_archive(label: str, names: list[str], read: object) -> int:
    """아카이브 하나의 번들 데이터 정합성을 검사한다."""
    index_names = [n for n in names if INDEX_JSON.search(n)]
    body_names = [n for n in names if ARTICLE_MD.search(n)]

    if len(index_names) != 1:
        return _fail(f"{label}: 인덱스가 정확히 1개가 아님 ({len(index_names)}개)")
    if not body_names:
        return _fail(f"{label}: 본문 마크다운이 하나도 없음 — 데이터 번들 누락")

    index = json.loads(read(index_names[0]).decode("utf-8"))
    records = index["articles"]
    count = index["count"]

    if count != len(records):
        return _fail(f"{label}: count({count}) != 레코드 수({len(records)})")
    if count != len(body_names):
        return _fail(f"{label}: count({count}) != 본문 파일 수({len(body_names)})")

    indexed = {record["file"] for record in records}
    bundled = {Path(n).name for n in body_names}
    if indexed != bundled:
        missing = sorted(indexed - bundled)
        extra = sorted(bundled - indexed)
        return _fail(f"{label}: 인덱스 ↔ 번들 불일치 missing={missing} extra={extra}")

    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        return _fail(f"{label}: 중복 id")
    urls = [record["url"] for record in records]
    if len(urls) != len(set(urls)):
        return _fail(f"{label}: 중복 URL")

    # fail-closed: 홈 폴백 URL이 섞여 있으면 오도성 출처 링크가 나간다.
    home_fallback = [r["id"] for r in records if not r.get("published")]
    if home_fallback:
        return _fail(f"{label}: 정식 게시 URL 없는 글이 포함됨 {home_fallback}")

    print(f"✅ {label}: {count}편 (인덱스 ↔ 번들 일치, 중복 0, 전부 정식 게시글)")
    return 0


def check_artifacts(dist_dir: Path) -> int:
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return _fail(
            f"{dist_dir}: wheel 1개 + sdist 1개를 기대했으나 "
            f"wheel={len(wheels)}, sdist={len(sdists)} — 먼저 `rm -rf dist && uv build`"
        )

    with zipfile.ZipFile(wheels[0]) as zf:
        if _check_archive(f"wheel({wheels[0].name})", zf.namelist(), zf.read):
            return 1
    with tarfile.open(sdists[0]) as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]

        def read(name: str) -> bytes:
            extracted = tf.extractfile(name)
            assert extracted is not None
            return extracted.read()

        if _check_archive(f"sdist({sdists[0].name})", names, read):
            return 1
    return 0


def check_installed() -> int:
    """설치된 패키지만으로 코퍼스와 MCP 도구가 동작하는지 확인한다."""
    from aiarchitect_blog_mcp.corpus import Corpus, is_published

    corpus = Corpus()
    served = len(corpus.records)
    if served == 0:
        return _fail("설치본: 서빙 글 0편 — 데이터 번들이 설치되지 않았다")
    if corpus.excluded_ids:
        return _fail(f"설치본: fail-closed 제외 대상이 번들에 남아 있음 {corpus.excluded_ids}")
    if not all(is_published(r["url"]) for r in corpus.records):
        return _fail("설치본: 홈 폴백 URL이 서빙되고 있음")

    # 검색 → 본문 → 백링크까지 실제 경로를 한 번 통과시킨다.
    sample = corpus.records[-1]
    rendered = corpus.render_article(sample["id"])
    if not rendered.startswith("# "):
        return _fail(f"설치본: 본문이 H1로 시작하지 않음 (id={sample['id']})")
    if rendered.count(sample["url"]) < 2:
        return _fail(f"설치본: 원문 링크·백링크 누락 (id={sample['id']})")
    if not corpus.search("MCP", limit=1):
        return _fail("설치본: 검색 결과 없음")

    from aiarchitect_blog_mcp.server import mcp  # noqa: F401  (임포트 가능 여부 확인)

    print(f"✅ 설치본: {served}편 서빙 · 검색 · 본문/백링크(id={sample['id']}) 정상")
    return 0


def main(argv: list[str]) -> int:
    if "--installed" in argv:
        return check_installed()
    args = [a for a in argv if not a.startswith("--")]
    return check_artifacts(Path(args[0]) if args else Path("dist"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
