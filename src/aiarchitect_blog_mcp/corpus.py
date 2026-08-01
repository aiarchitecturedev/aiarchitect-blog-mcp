"""블로그 코퍼스 파싱·검색.

공개 저장소의 마크다운 글(헤더 블록 + 본문)을 파싱해 메타데이터 인덱스를 만들고,
목록/검색/열람을 제공한다. 헤더 포맷은 게시/초안/확장 3변형이 섞여 있어 세 변형을 모두 흡수한다.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BLOG_HOME = "https://aiarchitect.tistory.com/"
DATA_DIR = Path(__file__).parent / "data"

# 헤더 블록에 등장하는 알려진 필드명(본문 bullet과 구분하기 위한 화이트리스트)
_META_KEYS = {
    "문서 ID", "상태", "Tistory 상태", "분류", "공개일", "공개 URL",
    "제목", "권장 제목", "검색 설명", "태그", "권장 태그",
    "권장 대표 이미지", "도식 정책", "작성 기준", "Tistory 글 번호",
}
_BULLET = re.compile(r"^-\s*([^:：]+?)\s*[:：]\s*(.*)$")


def _strip_ticks(s: str) -> str:
    return s.strip().strip("`").strip()


def parse_metadata(text: str) -> dict[str, str]:
    """상단 bullet 헤더에서 알려진 필드만 추출한다(첫 등장 우선)."""
    fields: dict[str, str] = {}
    for ln in text.splitlines()[:30]:
        m = _BULLET.match(ln)
        if not m:
            continue
        key = _strip_ticks(m.group(1))
        if key in _META_KEYS and key not in fields:
            fields[key] = m.group(2).strip()
    return fields


def extract_body(text: str) -> str:
    """헤더 블록(H1 + 메타 bullet) 이후의 본문만 반환한다."""
    lines = text.splitlines()
    last_meta = -1
    for i, ln in enumerate(lines[:30]):
        m = _BULLET.match(ln)
        if m and _strip_ticks(m.group(1)) in _META_KEYS:
            last_meta = i
    body = lines[last_meta + 1:]
    # 선행 공백/구분선(---) 제거
    while body and (not body[0].strip() or body[0].strip() == "---"):
        body.pop(0)
    return "\n".join(body).strip()


def build_record(path: Path) -> dict:
    """마크다운 파일 → 인덱스 레코드(메타데이터)."""
    text = path.read_text(encoding="utf-8")
    f = parse_metadata(text)

    doc_id = _strip_ticks(f.get("문서 ID", ""))
    m = re.search(r"BLOG-(\d+)", doc_id)
    num = m.group(1) if m else path.name[:2]

    title = _strip_ticks(f.get("권장 제목") or f.get("제목") or path.stem)
    category = _strip_ticks(f.get("분류", ""))
    description = _strip_ticks(f.get("검색 설명", ""))
    tags_raw = f.get("권장 태그") or f.get("태그") or ""
    tags = [_strip_ticks(t) for t in tags_raw.split(",") if _strip_ticks(t)]

    url = _strip_ticks(f.get("공개 URL", ""))
    if not url or "미발급" in url or not url.startswith("http"):
        url = BLOG_HOME  # 미게시(예: 발급 전) 글은 블로그 홈으로 폴백

    return {
        "id": num,
        "doc_id": doc_id or f"BLOG-{num}",
        "title": title,
        "category": category,
        "description": description,
        "tags": tags,
        "url": url,
        "file": path.name,
    }


class Corpus:
    """번들된 인덱스(articles_index.json) + 본문 마크다운을 로드해 조회를 제공한다."""

    def __init__(self, data_dir: Path | str = DATA_DIR):
        self.data_dir = Path(data_dir)
        index_path = self.data_dir / "articles_index.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"인덱스가 없습니다: {index_path}. 먼저 `python scripts/build_index.py`를 실행하세요."
            )
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.records: list[dict] = index["articles"]
        self._by_id = {r["id"]: r for r in self.records}
        self._body_cache: dict[str, str] = {}

    # --- 내부 헬퍼 ---
    def _norm_id(self, article_id) -> str:
        s = str(article_id).upper().replace("BLOG-", "").strip()
        return s.zfill(2) if s.isdigit() else s

    def _body(self, rec: dict) -> str:
        rid = rec["id"]
        if rid not in self._body_cache:
            text = (self.data_dir / "articles" / rec["file"]).read_text(encoding="utf-8")
            self._body_cache[rid] = extract_body(text)
        return self._body_cache[rid]

    def _summary(self, rec: dict) -> dict:
        return {
            "id": rec["id"],
            "doc_id": rec["doc_id"],
            "title": rec["title"],
            "category": rec["category"],
            "tags": rec["tags"],
            "url": rec["url"],
        }

    def _snippet(self, rec: dict, terms: list[str], width: int = 220) -> str:
        body = self._body(rec)
        low = body.lower()
        pos = min((low.find(t) for t in terms if t in low), default=-1)
        if pos < 0:
            return (rec["description"] or body[:width]).strip()
        start = max(0, pos - width // 3)
        seg = body[start:start + width].strip().replace("\n", " ")
        return ("…" if start > 0 else "") + seg + "…"

    # --- 공개 API ---
    def categories(self) -> list[dict]:
        c = Counter(r["category"] for r in self.records if r["category"])
        return [{"category": k, "count": v} for k, v in sorted(c.items(), key=lambda x: (-x[1], x[0]))]

    def list_articles(self, category: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        recs = self.records
        if category:
            recs = [r for r in recs if r["category"] == category or category in r["category"]]
        return [self._summary(r) for r in recs[offset:offset + limit]]

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict]:
        terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]
        if not terms:
            return []
        scored: list[tuple[int, dict]] = []
        for r in self.records:
            if category and not (r["category"] == category or category in r["category"]):
                continue
            title = r["title"].lower()
            tags = " ".join(r["tags"]).lower()
            desc = r["description"].lower()
            body = self._body(r).lower()
            score = 0
            for t in terms:
                score += title.count(t) * 5 + tags.count(t) * 4 + desc.count(t) * 3 + body.count(t)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        out = []
        for score, r in scored[:limit]:
            item = self._summary(r)
            item["score"] = score
            item["snippet"] = self._snippet(r, terms)
            out.append(item)
        return out

    def render_article(self, article_id) -> str:
        rec = self._by_id.get(self._norm_id(article_id))
        if not rec:
            return (
                f"글을 찾을 수 없습니다: {article_id!r}. "
                f"list_articles() 또는 search_articles()로 유효한 id를 확인하세요."
            )
        body = self._body(rec)
        tags = ", ".join(rec["tags"])
        header = (
            f"# {rec['title']}\n\n"
            f"> 📖 **원문(정식 게시글)**: {rec['url']}\n"
            f"> 🏷️ 분류: {rec['category']}"
            + (f" · 태그: {tags}" if tags else "")
            + f"\n> ✍️ AI아키텍트 · {BLOG_HOME}\n\n---\n\n"
        )
        footer = (
            f"\n\n---\n"
            f"📌 이 글의 원문 및 다른 기술 글: {rec['url']}\n"
            f"🔗 블로그: {BLOG_HOME} (AI아키텍트)\n"
        )
        return header + body + footer
