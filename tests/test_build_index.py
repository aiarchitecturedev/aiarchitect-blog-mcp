"""인덱스 생성기의 파괴적 교체 전 프리플라이트 테스트."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "build_index.py"
SPEC = importlib.util.spec_from_file_location("build_index", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
build_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_index)


def test_expected_ids_are_exactly_01_through_69():
    assert build_index.EXPECTED_IDS == tuple(f"{number:02d}" for number in range(1, 70))


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
