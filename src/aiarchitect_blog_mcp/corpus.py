"""블로그 코퍼스 파싱·검색.

공개 저장소의 마크다운 글(헤더 블록 + 본문)을 파싱해 메타데이터 인덱스를 만들고,
목록/검색/열람을 제공한다. 헤더 포맷은 게시/초안/확장 3변형이 섞여 있어 세 변형을 모두 흡수한다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

BLOG_HOME = "https://aiarchitect.tistory.com/"
DATA_DIR = Path(__file__).parent / "data"

# 개별 게시글 URL 패턴(홈 폴백과 구분). 공개 배포 fail-closed 판정 기준.
# 글 번호는 ASCII 양의 정수만 허용(`/0`·`/00`·전각·아랍 등 Unicode 숫자 거부).
_ARTICLE_URL = re.compile(r"^https://aiarchitect\.tistory\.com/[1-9][0-9]*/?$")

# 랭킹 파라미터(BM25 관례값).
# k1: 빈도 포화 — "ai"가 249번 나온 글이 1번 나온 글의 249배가 되지 않게 한다.
# b : 길이 정규화 강도 — 긴 글이 빈도만으로 유리해지는 것을 보정한다.
# (글, 검색어)별 빈도 캐시 상한. 임의의 질의어가 계속 들어와도 메모리가 무한정 늘지 않게 한다.
_TF_CACHE_MAX = 50_000

_BM25_K1 = 1.2
_BM25_B = 0.75

# 검색어 일치 규칙: **선두 경계만** 요구한다.
# 한국어는 교착어라 조사·어미가 붙는다("로그를"·"평가합니다") — 뒤는 열어 둬야 한다.
# 반면 앞을 열어 두면 "블로그"가 "로그"에, "chain"이 "ai"에 걸린다(코퍼스의 '로그' 일치 중 28%가 이런 오탐).
_TERM_BOUNDARY = r"(?<![0-9a-z가-힣])"


def _idf(total: int, df: int) -> float:
    """역문서빈도. 전체 total편 중 df편에 나오는 단어의 가중치.

    흔한 단어일수록 0에 가까워진다 — 거의 모든 글에 있는 단어는 글을 구분해 주지 않는다.
    """
    return math.log(1 + (total - df + 0.5) / (df + 0.5))


def _bm25_tf(tf: int, length: int, avg_len: float) -> float:
    """BM25의 빈도 항 — 포화 + 길이 정규화.

    포화(k1): 같은 단어가 100번 나왔다고 1번의 100배가 되지 않는다.
    길이 정규화(b): 같은 빈도라면 짧은 글이 더 밀도 높게 다룬 것으로 본다.
    """
    norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * length / (avg_len or 1.0))
    return tf * (_BM25_K1 + 1) / (tf + norm)


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(_TERM_BOUNDARY + re.escape(term))


def _term_count(text: str, term: str) -> int:
    """소문자 텍스트에서 term의 출현 횟수(선두 경계 규칙 적용).

    정규식은 substring 검색보다 훨씬 비싸다. 대부분의 (글, 검색어) 조합은 아예
    일치가 없으므로, 먼저 C 레벨 substring 검색으로 걸러내고 있을 때만 정규식을 쓴다.
    """
    if term not in text:
        return 0
    return len(_term_pattern(term).findall(text))


# 입력 검증 상한(방어적 클램프)
MAX_LIST_LIMIT = 200
MAX_SEARCH_LIMIT = 50


def is_published(url: str) -> bool:
    """URL이 정식 게시글(홈 폴백이 아닌 개별 글)인지 판정한다.

    공개 배포 빌드·서빙에서 정식 게시 URL이 없는 글을 노출하지 않기 위한
    fail-closed 기준. 홈 URL·빈 값·비문자열·비정상 값은 모두 False.
    """
    if not isinstance(url, str):
        return False
    return bool(_ARTICLE_URL.match(url.strip()))


def _clamp_int(value, default: int, lo: int, hi: int) -> int:
    """정수로 강제 변환 후 [lo, hi]로 클램프한다. 변환 실패 시 default를 반환한다.

    bool은 정수로 인정하지 않고(True/False 오입력 방어), float('inf')·NaN 등
    변환 불가 값(OverflowError·ValueError)은 default로 되돌린다.
    """
    if isinstance(value, bool):
        return default
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(lo, min(n, hi))

# 헤더 블록에 등장하는 알려진 필드명(본문 bullet과 구분하기 위한 화이트리스트)
_META_KEYS = {
    "문서 ID", "상태", "Tistory 상태", "분류", "공개일", "공개 URL",
    "제목", "권장 제목", "게시 제목", "검색 설명", "태그", "권장 태그",
    "권장 대표 이미지", "도식 정책", "작성 기준", "Tistory 글 번호",
}
_BULLET = re.compile(r"^-\s*([^:：]+?)\s*[:：]\s*(.*)$")
# 소스 파일명 선두의 글 번호(1~3자리) — 문서 ID가 없을 때의 폴백.
_FILE_NUMBER = re.compile(r"^(\d{1,3})-")


def _id_sort_key(article_id: str) -> tuple[int, str]:
    """id 동점 정렬 키. 숫자 id는 숫자 크기순(…"11" < "100"), 그 외는 사전순 뒤쪽."""
    s = str(article_id)
    return (int(s), "") if s.isdigit() else (1 << 30, s)


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


# 내부 헤더 블록이 끝나는 지점(실제 H1)을 찾을 때 훑는 범위. 실측 15~25행.
_HEADER_WINDOW = 40


def _internal_header_end(lines: list[str]) -> int:
    """내부 헤더 블록 다음에 오는 실제 본문 H1의 줄 번호. 없으면 -1.

    소스 글은 `보일러플레이트 H1` + 편집용 메타 bullet + `---` + 실제 H1 구조다.
    메타 bullet 키는 글마다 제각각이라 화이트리스트로 헤더의 끝을 정하면 모르는 키가
    공개 본문으로 샌다. 그래서 끝은 **구조**로 정한다 — 보일러플레이트 H1 다음에
    오는 두 번째 H1부터가 공개 본문이다. 화이트리스트는 "편집용 헤더가 존재한다"는
    신호로만 쓴다(일반 본문 오탐 방지).
    """
    if not lines or not lines[0].startswith("# "):
        return -1
    for i, ln in enumerate(lines[1:_HEADER_WINDOW], start=1):
        if ln.startswith("# "):
            head = lines[1:i]
            has_meta = any(
                (m := _BULLET.match(x)) and _strip_ticks(m.group(1)) in _META_KEYS
                for x in head
            )
            return i if has_meta else -1
    return -1


def extract_body(text: str) -> str:
    """헤더 블록(H1 + 메타 bullet) 이후의 본문만 반환한다.

    번들된 글은 이미 정제돼 실제 H1로 시작하므로 그대로 돌려준다(서빙 경로 무변경).
    """
    lines = text.splitlines()
    start = _internal_header_end(lines)
    if start >= 0:
        return "\n".join(lines[start:]).strip()

    # 내부 헤더 구조가 아닌 경우(정제된 번들 본문·변형 헤더): 알려진 메타 bullet까지만 잘라낸다.
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
    m = re.search(r"BLOG-(\d+)", doc_id) or _FILE_NUMBER.match(path.name)
    # id는 티스토리 글 번호와 같다. 소스 표기(BLOG-7 / 07-...)에 상관없이 2자리로 정규화해
    # Corpus._norm_id의 조회 키와 일치시킨다(100 이상은 그대로).
    num = f"{int(m.group(1)):02d}" if m else path.stem

    # 제목 키는 글마다 다르다(게시 제목 = 실제 게시본, 권장 제목 = 초안 권장안).
    title = _strip_ticks(
        f.get("게시 제목") or f.get("권장 제목") or f.get("제목") or path.stem
    )
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
        "published": is_published(url),
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
        raw: list[dict] = index["articles"]
        # fail-closed: 정식 게시 URL이 없는(홈 폴백) 글은 목록·검색·본문 어디에도 노출하지 않는다.
        self.records: list[dict] = [r for r in raw if self._is_published_rec(r)]
        self.excluded_ids: list[str] = [r.get("id") for r in raw if not self._is_published_rec(r)]
        self._by_id = {r["id"]: r for r in self.records}
        self._body_cache: dict[str, str] = {}
        self._lower_cache: dict[str, str] = {}
        self._avg_len: float | None = None
        self._tf_cache: dict[tuple[str, str], int] = {}

    # --- 내부 헬퍼 ---
    @staticmethod
    def _is_published_rec(rec: dict) -> bool:
        """레코드가 정식 게시글인지 판정한다(엄밀 fail-closed).

        URL이 정식 게시글 형식이어야 하며(홈 폴백·외부 도메인 거부), 동시에
        `published` 플래그가 엄격히 `True`여야 한다. 플래그가 없으면 URL 판정만 적용.
        문자열 `"false"`·홈 URL+참 플래그 같은 우회 조합을 모두 차단한다.
        """
        return is_published(rec.get("url", "")) and rec.get("published", True) is True

    def _norm_id(self, article_id) -> str:
        s = str(article_id).upper().replace("BLOG-", "").strip()
        return s.zfill(2) if s.isdigit() else s

    def _body(self, rec: dict) -> str:
        rid = rec["id"]
        if rid not in self._body_cache:
            text = (self.data_dir / "articles" / rec["file"]).read_text(encoding="utf-8")
            self._body_cache[rid] = extract_body(text)
        return self._body_cache[rid]

    def _lower_body(self, rec: dict) -> str:
        rid = rec["id"]
        if rid not in self._lower_cache:
            self._lower_cache[rid] = self._body(rec).lower()
        return self._lower_cache[rid]

    def _weighted_tf(self, rec: dict, term: str) -> int:
        """필드 가중 빈도. 코퍼스가 불변이라 (글, 검색어)당 한 번만 센다.

        캐시가 무한정 자라지 않게 상한을 두고, 넘으면 통째로 비운다(재계산 가능한 값).
        """
        key = (rec["id"], term)
        cached = self._tf_cache.get(key)
        if cached is not None:
            return cached
        tf = (
            _term_count(rec["title"].lower(), term) * 5
            + _term_count(" ".join(rec["tags"]).lower(), term) * 4
            + _term_count(rec["description"].lower(), term) * 3
            + _term_count(self._lower_body(rec), term)
        )
        if len(self._tf_cache) >= _TF_CACHE_MAX:
            self._tf_cache.clear()
        self._tf_cache[key] = tf
        return tf

    def _average_length(self) -> float:
        """길이 정규화 기준이 되는 평균 본문 길이(최초 1회 계산 후 캐시)."""
        if self._avg_len is None:
            lengths = [len(self._lower_body(r)) for r in self.records]
            self._avg_len = (sum(lengths) / len(lengths)) if lengths else 1.0
        return self._avg_len or 1.0

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
        limit = _clamp_int(limit, 50, 0, MAX_LIST_LIMIT)
        offset = _clamp_int(offset, 0, 0, 10_000_000)
        recs = self.records
        if category:
            recs = [r for r in recs if r["category"] == category or category in r["category"]]
        return [self._summary(r) for r in recs[offset:offset + limit]]

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict]:
        limit = _clamp_int(limit, 10, 0, MAX_SEARCH_LIMIT)
        terms = [t for t in re.split(r"\s+", str(query).lower().strip()) if t]
        if not terms or limit == 0:
            return []
        candidates = [
            r for r in self.records
            if not category or r["category"] == category or category in r["category"]
        ]
        if not candidates:
            return []

        # 필드 가중 빈도. 제목·태그·설명은 짧고 신호가 강해 가중치를 크게 준다.
        weighted = [{t: self._weighted_tf(r, t) for t in terms} for r in candidates]

        # IDF: 흔한 단어가 희귀한 단어를 덮지 않게 한다.
        # 이것이 없으면 "RAG 청킹"에서 청킹이 한 번도 안 나오는 글이 rag 빈도만으로 상위에 온다.
        total = len(candidates)
        idf = {t: _idf(total, sum(1 for tf in weighted if tf[t] > 0)) for t in terms}

        avg_len = self._average_length()
        scored: list[tuple[float, dict]] = []
        for r, tf_map in zip(candidates, weighted):
            length = len(self._lower_body(r)) or 1
            score = 0.0
            for t in terms:
                tf = tf_map[t]
                if tf:
                    score += idf[t] * _bm25_tf(tf, length, avg_len)
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: (-x[0], _id_sort_key(x[1]["id"])))
        out = []
        for score, r in scored[:limit]:
            item = self._summary(r)
            item["score"] = round(score, 3)
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
