#!/usr/bin/env python3
"""정본 소스 ↔ 번들 코퍼스 drift 점검(읽기 전용 — 아무것도 쓰지 않는다).

정본 소스는 **다른 저장소**에 있다. 글이 늘어도, 고쳐 발행돼도 이 저장소는 모른다.
`build_index.py`를 돌려 `git diff`를 보는 것이 가장 확실하지만 그건 산출물을 덮어쓴다 —
확인만 하려고 번들을 갈아 끼울 수는 없다. 여기서는 같은 파서로 "지금 재빌드하면 무엇이
달라지는가"만 계산해 보고한다.

⚠️ **편수 비교만으로는 부족하다.** 2026-11-18, BLOG-89·90이 3개월째 공개돼 있는데도
번들에서 빠져 있는 것이 드러났다. 소스 96편 · 번들 94편은 그동안 "알려진 제외 2편"으로
보여 아무 신호도 주지 않았다 — 두 글은 URL이 `공개 URL`이 아니라 `Tistory 상태` 줄에
섞여 있어 파서가 홈 폴백으로 읽었을 뿐이다. 그래서 ②는 **키 이름을 가리지 않고** 헤더
전체에서 정식 게시 URL을 찾아 파서가 읽은 값과 대조한다. 양식을 외우지 않기 위해서다.

사용:
    python scripts/check_corpus_drift.py /path/to/blogs

종료 코드: 0 = 일치 · 1 = drift 있음 · 2 = 점검 불가(fail-closed)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 설치 없이 패키지 파서를 임포트할 수 있도록 src를 경로에 추가
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aiarchitect_blog_mcp import corpus as _corpus  # noqa: E402
from aiarchitect_blog_mcp.corpus import (  # noqa: E402
    build_record,
    extract_body,
    is_published,
    strip_publishing_scaffolding,
)

DATA_DIR = _ROOT / "src" / "aiarchitect_blog_mcp" / "data"
# 헤더 줄 어디에 섞여 있어도 잡는다(`공개 URL:` 키에 한정하지 않는다).
# 정식 게시글인지는 찾은 뒤 is_published로 판정한다 — 홈 URL·모바일 경로는 걸러진다.
_URL_ANYWHERE = re.compile(r"https://aiarchitect\.tistory\.com/\d+/?")
# 메타 비교 대상 필드. 번들 인덱스에 실려 서빙에 쓰이는 값들.
_RECORD_FIELDS = ("title", "category", "description", "tags", "url", "published", "doc_id")


def header_lines(text: str) -> list[str]:
    """내부 편집 헤더 블록의 줄들. 경계는 화이트리스트가 아니라 **구조**로 정한다.

    `_internal_header_end`는 "보일러플레이트 H1 다음에 오는 두 번째 H1"을 본문 시작으로
    본다. 모르는 키가 새로 생겨도 헤더 범위는 그대로 잡힌다(키 목록으로 자르면 샌다).
    구조가 아닌 글(정제된 번들 본문 등)은 헤더가 없으므로 빈 목록이다.
    """
    lines = text.splitlines()
    end = _corpus._internal_header_end(lines)
    return lines[1:end] if end > 0 else []


def meta_article_urls(text: str) -> list[tuple[str, str]]:
    """헤더에서 발견되는 (키, 정식 게시 URL) 쌍 전부. 키 이름을 가리지 않는다."""
    found: list[tuple[str, str]] = []
    for ln in header_lines(text):
        m = _corpus._BULLET.match(ln)
        if not m:
            continue
        key = _corpus._strip_ticks(m.group(1))
        for url in _URL_ANYWHERE.findall(m.group(2)):
            if is_published(url):
                found.append((key, url))
    return found


def bundled_body_path(data_dir: Path, file_name: str) -> Path:
    return data_dir / "articles" / file_name


def source_body(text: str) -> str:
    """build_index.py가 번들에 쓰는 것과 **같은** 본문을 만든다(비교 기준 일치)."""
    return strip_publishing_scaffolding(extract_body(text)).rstrip() + "\n"


def source_files(src: Path) -> list[Path]:
    return sorted(
        (p for p in src.glob("[0-9]*-*.md") if _corpus._FILE_NUMBER.match(p.name)),
        key=lambda p: int(_corpus._FILE_NUMBER.match(p.name).group(1)),
    )


def compare(src: Path, data_dir: Path = DATA_DIR) -> dict:
    """소스와 번들을 대조한 리포트를 돌려준다(파일을 쓰지 않는다)."""
    index = json.loads((data_dir / "articles_index.json").read_text(encoding="utf-8"))
    bundled = {r["id"]: r for r in index["articles"]}

    added: list[dict] = []        # 소스에만 있는 글(번들에 없음)
    removed: list[str] = []       # 번들에만 있는 글(소스에서 사라짐)
    body_changed: list[str] = []  # 본문이 달라진 글
    meta_changed: list[dict] = []  # 메타가 달라진 글
    url_mismatch: list[dict] = []  # 🔴 파서가 읽은 URL ↔ 헤더에 있는 URL 불일치
    excluded: list[dict] = []     # fail-closed 제외(정식 게시 URL 없음)
    unverified: list[dict] = []   # 헤더 구조를 못 읽어 ②를 적용하지 못한 파일

    seen: set[str] = set()
    for path in source_files(src):
        text = path.read_text(encoding="utf-8")
        record = build_record(path)
        article_id = record["id"]
        seen.add(article_id)

        # ② 키 이름을 가리지 않은 URL 재검증 — 제외된 글이든 서빙 중인 글이든 똑같이 본다.
        # 🔴 헤더 구조를 못 읽으면 "URL 없음"이 아니라 "검사 못 함"이다. 조용히 넘기지 않는다.
        if not header_lines(text):
            unverified.append({"id": article_id, "file": path.name})
        header_urls = {u for _, u in meta_article_urls(text)}
        parsed = record["url"] if record["published"] else ""
        if header_urls and parsed not in header_urls:
            url_mismatch.append({
                "id": article_id,
                "file": path.name,
                "parsed": record["url"],
                "published": record["published"],
                "found": sorted(meta_article_urls(text), key=lambda kv: kv[1]),
            })

        if not record["published"]:
            excluded.append({"id": article_id, "file": path.name, "url": record["url"]})

        prior = bundled.get(article_id)
        if prior is None:
            if record["published"]:
                added.append({"id": article_id, "file": path.name, "title": record["title"]})
            continue

        diffs = {
            field: (prior.get(field), record.get(field))
            for field in _RECORD_FIELDS
            if prior.get(field) != record.get(field)
        }
        if diffs:
            meta_changed.append({"id": article_id, "file": path.name, "diffs": diffs})

        body_file = bundled_body_path(data_dir, prior["file"])
        if not body_file.exists():
            body_changed.append(article_id)
        elif body_file.read_text(encoding="utf-8") != source_body(text):
            body_changed.append(article_id)

    removed = sorted(set(bundled) - seen, key=_corpus._id_sort_key)

    return {
        "source_count": len(seen),
        "bundle_count": len(bundled),
        "added": added,
        "removed": removed,
        "body_changed": body_changed,
        "meta_changed": meta_changed,
        "url_mismatch": url_mismatch,
        "excluded": excluded,
        "unverified": unverified,
    }


def has_drift(report: dict) -> bool:
    """재빌드가 번들을 바꾸거나, 제외 판정이 소스와 어긋나면 drift다."""
    return any(
        report[k]
        for k in ("added", "removed", "body_changed", "meta_changed", "url_mismatch", "unverified")
    )


def render(report: dict, src: Path, data_dir: Path) -> list[str]:
    out = [
        "🔎 소스 ↔ 번들 drift 점검",
        f"   소스: {src} ({report['source_count']}편)",
        f"   번들: {data_dir} ({report['bundle_count']}편)",
        "",
        "① 글 집합",
    ]
    if report["added"]:
        for a in report["added"]:
            out.append(f"   🆕 신규(소스에만): {a['id']} — {a['title']} [{a['file']}]")
    if report["removed"]:
        out.append(f"   🗑️ 번들에만 남음(소스에서 사라짐): {', '.join(report['removed'])}")
    if not report["added"] and not report["removed"]:
        out.append("   ✅ 추가·삭제 없음")
    if report["excluded"]:
        ids = ", ".join(e["id"] for e in report["excluded"])
        out.append(f"   🔒 fail-closed 제외 {len(report['excluded'])}편: {ids}")

    out += ["", "② 게시 URL 재검증 (메타 키 이름을 가리지 않음)"]
    if report["url_mismatch"]:
        for u in report["url_mismatch"]:
            state = "서빙 중" if u["published"] else "제외됨(홈 폴백)"
            out.append(f"   🔴 {u['id']} [{u['file']}] — 파서가 읽은 URL: {u['parsed']} ({state})")
            for key, url in u["found"]:
                out.append(f"        헤더 「{key}」 에 정식 게시 URL: {url}")
            if not u["published"]:
                out.append("        → 소스에 `- 공개 URL: <그 주소>` 를 넣으면 서빙 대상이 된다")
    elif not report["unverified"]:
        out.append("   ✅ 파서가 읽은 URL과 헤더의 게시 URL이 모두 일치")
    for u in report["unverified"]:
        out.append(
            f"   ⚠️ {u['id']} [{u['file']}] — 편집 헤더 구조를 못 읽어 검사하지 못했다"
        )

    out += ["", f"③ 본문 변경 — {len(report['body_changed'])}편"]
    if report["body_changed"]:
        out.append(f"   📝 {', '.join(report['body_changed'])}")

    out += ["", f"④ 메타 변경 — {len(report['meta_changed'])}편"]
    for m in report["meta_changed"]:
        for field, (old, new) in m["diffs"].items():
            out.append(f"   📝 {m['id']} {field}: {old!r} → {new!r}")

    out += [""]
    if has_drift(report):
        n = (
            len(report["added"]) + len(report["removed"]) + len(report["body_changed"])
            + len(report["meta_changed"]) + len(report["url_mismatch"])
            + len(report["unverified"])
        )
        out.append(f"결과: 🔴 drift {n}건 — 절차는 CORPUS_RUNBOOK.md")
    else:
        out.append("결과: ✅ 번들이 소스와 일치(재빌드해도 달라지지 않는다)")
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(argv[0]).expanduser()
    if not src.is_dir():
        print(f"❌ 소스 디렉터리 없음: {src}", file=sys.stderr)
        return 2
    if not (DATA_DIR / "articles_index.json").exists():
        print(f"❌ 번들 인덱스 없음: {DATA_DIR / 'articles_index.json'}", file=sys.stderr)
        return 2
    if not source_files(src):
        print(f"❌ 마크다운 글을 찾지 못함: {src}", file=sys.stderr)
        return 2

    report = compare(src, DATA_DIR)
    print("\n".join(render(report, src, DATA_DIR)))
    return 1 if has_drift(report) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
