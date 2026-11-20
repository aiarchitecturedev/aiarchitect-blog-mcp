"""정본 소스 ↔ 번들 drift 검사기 — 합성 코퍼스로 돌아가므로 CI에서도 실행된다.

실제 정본 소스는 **다른 저장소**에 있어 러너에 없다. 여기서는 소스·번들 한 쌍을
tmp에 만들어 **검사기의 동작**을 검증한다. 각 테스트는 한쪽만 틀어 놓고 그 변화를
집어내는지 본다 — "통과했다"와 "아무것도 안 봤다"를 구분하기 위해서다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "check_corpus_drift.py"
SPEC = importlib.util.spec_from_file_location("check_corpus_drift", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
drift = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drift)

ARTICLE_URL = "https://aiarchitect.tistory.com/{n}"
HOME_URL = "https://aiarchitect.tistory.com/"


def _source_article(n: int, *, title: str = "합성 글", body: str = "본문 문단입니다.",
                    url_key: str = "공개 URL", extra: str = "") -> str:
    """정본 소스와 같은 2-H1 구조(보일러플레이트 H1 + 메타 + `---` + 실제 H1)."""
    url_line = f"- {url_key}: {ARTICLE_URL.format(n=n)}" if url_key else ""
    lines = [
        "# Tistory 기술자료 초안",
        "",
        f"- 문서 ID: BLOG-{n}",
        "- 분류: 합성 분류",
        f"- 게시 제목: {title}",
        "- 검색 설명: 합성 설명",
    ]
    if url_line:
        lines.append(url_line)
    if extra:
        lines.append(extra)
    lines += ["", "---", "", f"# {title}", "", body, ""]
    return "\n".join(lines)


def _build_pair(tmp_path: Path, articles: dict[int, str]) -> tuple[Path, Path]:
    """소스 디렉터리와 **그것으로 만든** 번들을 함께 만든다(= drift 0 상태)."""
    src = tmp_path / "blogs"
    src.mkdir(exist_ok=True)
    for n, text in articles.items():
        (src / f"{n:02d}-synthetic.md").write_text(text, encoding="utf-8")
    data = tmp_path / "data"
    _rebuild(src, data)
    return src, data


def _rebuild(src: Path, data: Path) -> None:
    """build_index.py와 같은 변환으로 번들을 만든다(검사기의 기준점)."""
    (data / "articles").mkdir(parents=True, exist_ok=True)
    for old in (data / "articles").glob("*.md"):
        old.unlink()
    records = []
    for path in drift.source_files(src):
        record = drift.build_record(path)
        if not record["published"]:
            continue
        records.append(record)
        (data / "articles" / path.name).write_text(
            drift.source_body(path.read_text(encoding="utf-8")), encoding="utf-8"
        )
    (data / "articles_index.json").write_text(
        json.dumps({"source": HOME_URL, "count": len(records), "articles": records},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --- 기준선 -------------------------------------------------------------


def test_identical_source_and_bundle_report_no_drift(tmp_path):
    """소스와 번들이 같으면 drift 0. (이것이 성립해야 나머지 신호가 의미를 가진다)"""
    src, data = _build_pair(tmp_path, {7: _source_article(7), 8: _source_article(8)})
    report = drift.compare(src, data)
    assert report["source_count"] == 2 and report["bundle_count"] == 2
    assert not drift.has_drift(report)


# --- ① 글 집합 ----------------------------------------------------------


def test_new_source_article_is_detected(tmp_path):
    """정본에 글이 늘면 잡는다 — 이 검사기를 만든 이유(소스가 다른 저장소에 있다)."""
    src, data = _build_pair(tmp_path, {7: _source_article(7)})
    (src / "09-synthetic.md").write_text(_source_article(9, title="새 글"), encoding="utf-8")
    report = drift.compare(src, data)
    assert [a["id"] for a in report["added"]] == ["09"]
    assert report["added"][0]["title"] == "새 글"
    assert drift.has_drift(report)


def test_article_removed_from_source_is_detected(tmp_path):
    """번들에만 남은 글(소스에서 사라짐)도 신호다 — 조용히 유령을 서빙하지 않는다."""
    src, data = _build_pair(tmp_path, {7: _source_article(7), 8: _source_article(8)})
    (src / "08-synthetic.md").unlink()
    report = drift.compare(src, data)
    assert report["removed"] == ["08"]
    assert drift.has_drift(report)


# --- ② 게시 URL 재검증 (2026-11-18 회귀) --------------------------------


def test_published_url_in_unexpected_meta_key_is_detected(tmp_path):
    """🔴 BLOG-89·90 회귀 — URL이 `공개 URL`이 아닌 키에 있으면 3개월을 모른 채 지나간다.

    편수(소스 2 / 번들 1)는 "알려진 제외 1편"으로 보여 아무 신호도 주지 않는다.
    키 이름을 가리지 않고 헤더 전체를 보는 ②만이 이것을 잡는다.
    """
    src, data = _build_pair(tmp_path, {7: _source_article(7)})
    (src / "09-synthetic.md").write_text(
        _source_article(
            9,
            url_key="",  # `공개 URL` 키가 없다
            extra=f"- Tistory 상태: 공개 · {ARTICLE_URL.format(n=9)} · 검증 완료",
        ),
        encoding="utf-8",
    )
    report = drift.compare(src, data)

    assert [e["id"] for e in report["excluded"]] == ["09"]  # fail-closed는 정상 동작
    assert [u["id"] for u in report["url_mismatch"]] == ["09"]
    mismatch = report["url_mismatch"][0]
    assert mismatch["parsed"] == HOME_URL and mismatch["published"] is False
    assert mismatch["found"] == [("Tistory 상태", ARTICLE_URL.format(n=9))]
    assert drift.has_drift(report)


def test_same_url_in_two_keys_is_not_a_mismatch(tmp_path):
    """오탐 방지 — 68번처럼 `공개 URL`과 `Tistory 상태`에 **같은** 주소가 있는 글이 실재한다."""
    src, data = _build_pair(
        tmp_path,
        {7: _source_article(7, extra=f"- Tistory 상태: 공개 완료 · {ARTICLE_URL.format(n=7)} (검증)")},
    )
    report = drift.compare(src, data)
    assert report["url_mismatch"] == []
    assert not drift.has_drift(report)


def test_home_url_and_mobile_path_are_not_article_urls(tmp_path):
    """홈 URL·모바일 경로를 정식 게시 URL로 읽으면 엉뚱한 글이 서빙 대상이 된다."""
    text = _source_article(7, url_key="", extra=f"- Tistory 상태: 비공개 · {HOME_URL} · `/m/7` 확인")
    assert drift.meta_article_urls(text) == []


def test_body_links_to_other_articles_are_not_scanned(tmp_path):
    """본문은 ②의 대상이 아니다 — 글끼리 서로 링크하므로 본문을 보면 오탐이 쏟아진다."""
    text = _source_article(7, body=f"관련 글: {ARTICLE_URL.format(n=63)} 을 보세요.")
    assert drift.meta_article_urls(text) == [("공개 URL", ARTICLE_URL.format(n=7))]


def test_unreadable_header_is_reported_not_passed(tmp_path):
    """🔴 fail-closed — 헤더 구조를 못 읽으면 "URL 없음"이 아니라 "검사 못 함"이다."""
    src, data = _build_pair(tmp_path, {7: _source_article(7)})
    # 보일러플레이트 H1을 지우면 2-H1 구조가 깨진다(= ②를 적용할 수 없다)
    path = src / "07-synthetic.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("# Tistory 기술자료 초안\n", ""), encoding="utf-8"
    )
    report = drift.compare(src, data)
    assert [u["id"] for u in report["unverified"]] == ["07"]
    assert drift.has_drift(report)


# --- ③④ 본문·메타 변경 --------------------------------------------------


def test_body_change_is_detected(tmp_path):
    """고쳐 발행된 글 — 편수도 메타도 그대로라 본문을 직접 대조해야만 보인다."""
    src, data = _build_pair(tmp_path, {7: _source_article(7)})
    (src / "07-synthetic.md").write_text(
        _source_article(7, body="문단을 통째로 고쳐 썼습니다."), encoding="utf-8"
    )
    report = drift.compare(src, data)
    assert report["body_changed"] == ["07"]
    assert report["meta_changed"] == []
    assert drift.has_drift(report)


def test_title_change_is_detected_with_old_and_new(tmp_path):
    """메타 변경은 필드·전후 값까지 보고한다(무엇을 고쳐야 하는지 바로 알도록)."""
    src, data = _build_pair(tmp_path, {7: _source_article(7, title="옛 제목")})
    (src / "07-synthetic.md").write_text(_source_article(7, title="새 제목"), encoding="utf-8")
    report = drift.compare(src, data)
    assert len(report["meta_changed"]) == 1
    diffs = report["meta_changed"][0]["diffs"]
    assert diffs["title"] == ("옛 제목", "새 제목")
    assert drift.has_drift(report)


def test_missing_bundled_body_file_is_detected(tmp_path):
    """인덱스에는 있는데 본문 파일이 없는 번들 — 설치한 쪽에서만 깨진다."""
    src, data = _build_pair(tmp_path, {7: _source_article(7)})
    (data / "articles" / "07-synthetic.md").unlink()
    report = drift.compare(src, data)
    assert report["body_changed"] == ["07"]


# --- 종료 코드 ----------------------------------------------------------


def test_main_exits_2_when_source_is_missing(tmp_path):
    """점검 불가를 0(일치)으로 돌려주면 "확인했다"는 거짓말이 된다."""
    assert drift.main([str(tmp_path / "없는디렉터리")]) == 2
    assert drift.main([]) == 2


def test_main_exits_2_when_source_has_no_articles(tmp_path):
    """글이 0편인 디렉터리를 가리켰을 때 "삭제 96편"이 아니라 점검 불가로 멈춘다."""
    (tmp_path / "blogs").mkdir()
    assert drift.main([str(tmp_path / "blogs")]) == 2
