"""인덱스 생성기의 파괴적 교체 전 프리플라이트 테스트."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "build_index.py"
SPEC = importlib.util.spec_from_file_location("build_index", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
build_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_index)


# build_index와 독립적으로 기대값을 다시 적는다(골든 테스트).
SOURCE_NUMBERS = [*range(1, 36), *range(38, 97), 99, 100]
UNPUBLISHED_NUMBERS = [89, 90]


def test_expected_source_ids_cover_every_numbered_article():
    """소스에 있어야 하는 글 번호(96편). 결번 36·37·97·98은 원본에 글이 없다."""
    assert build_index.EXPECTED_SOURCE_IDS == tuple(f"{n:02d}" for n in SOURCE_NUMBERS)
    assert len(build_index.EXPECTED_SOURCE_IDS) == 96


def test_expected_ids_exclude_unpublished_drafts():
    """서빙 대상(94편) = 소스 96편 - 정식 게시 URL 없는 초안 2편(fail-closed)."""
    expected = tuple(
        f"{n:02d}" for n in SOURCE_NUMBERS if n not in UNPUBLISHED_NUMBERS
    )
    assert build_index.EXPECTED_IDS == expected
    assert len(build_index.EXPECTED_IDS) == 94
    assert build_index.EXPECTED_UNPUBLISHED_IDS == ("89", "90")


def test_expected_category_counts_sum_to_the_served_article_count():
    assert sum(build_index.EXPECTED_CATEGORY_COUNTS.values()) == len(build_index.EXPECTED_IDS)


def test_three_digit_article_numbers_sort_after_two_digit_ones(tmp_path, monkeypatch):
    """글 번호는 사전순이 아니라 숫자순으로 읽혀야 한다("100"이 "11" 앞에 오면 안 된다)."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for name in ("09-a.md", "10-b.md", "100-c.md", "11-d.md"):
        (source_dir / name).write_text("# 제목\n", encoding="utf-8")

    files = sorted(
        (p for p in source_dir.glob("[0-9]*-*.md") if build_index._FILE_NUMBER.match(p.name)),
        key=lambda p: int(build_index._FILE_NUMBER.match(p.name).group(1)),
    )
    assert [p.name for p in files] == ["09-a.md", "10-b.md", "11-d.md", "100-c.md"]
    ids = [
        build_index._format_id(int(build_index._FILE_NUMBER.match(p.name).group(1)))
        for p in files
    ]
    assert ids == ["09", "10", "11", "100"]


def test_incomplete_source_fails_before_existing_data_is_changed(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "data"
    articles_dir = output_dir / "articles"
    source_dir.mkdir()
    articles_dir.mkdir(parents=True)

    (source_dir / "01-only.md").write_text("# 한 편뿐인 소스\n", encoding="utf-8")
    index_path = output_dir / "articles_index.json"
    article_path = articles_dir / "preserve.md"
    index_path.write_text("preserve-index", encoding="utf-8")
    article_path.write_text("preserve-article", encoding="utf-8")
    monkeypatch.setattr(build_index, "OUT_DIR", output_dir)

    assert build_index.main(Path(source_dir)) == 1
    assert index_path.read_text(encoding="utf-8") == "preserve-index"
    assert article_path.read_text(encoding="utf-8") == "preserve-article"
