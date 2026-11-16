"""익명성 스캐너 검사 — 합성 토큰으로 돌아가므로 CI에서도 실행된다.

실제 denylist(`.private-tokens`)는 비추적 파일이라 러너에 없다. 그래서 기존
토큰 테스트들은 CI에서 **skip**된다 — 스캐너 자체가 고장 나도 아무도 모른다.
여기서는 denylist를 주입해 **검사기의 동작**을 검증한다. 토큰 내용과 무관하므로
러너에서도 그대로 돈다.
"""

from __future__ import annotations

import importlib.util
import tarfile
import zipfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "scan_private_tokens.py"
SPEC = importlib.util.spec_from_file_location("scan_private_tokens", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)

# 실제 denylist와 무관한 합성 토큰. 이 저장소 어디에도 없는 문자열이어야 한다.
FAKE = ("zzz-secret-handle", "zzz-internal.example")


def _write_wheel(path: Path, payload: str) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("pkg/__init__.py", "# ok\n")
        zf.writestr("pkg/data.txt", payload)


def _write_sdist(path: Path, payload: str, tmp: Path) -> None:
    member = tmp / "data.txt"
    member.write_text(payload, encoding="utf-8")
    with tarfile.open(path, "w:gz") as tf:
        tf.add(member, arcname="pkg-0.0.0/data.txt")


def test_find_in_text_reports_indexes_not_token_text():
    """히트는 토큰 문자열이 아니라 인덱스로 보고한다(스캐너가 토큰을 흘리지 않게)."""
    assert scan.find_in_text("무해한 문장", FAKE) == []
    assert scan.find_in_text(f"경로: {FAKE[0]}/x", FAKE) == [0]
    assert scan.find_in_text(f"{FAKE[1]} 그리고 {FAKE[0]}", FAKE) == [0, 1]


def test_match_is_case_insensitive():
    """소스가 대문자로 적어도 잡아야 한다."""
    assert scan.find_in_text(FAKE[0].upper(), FAKE) == [0]


def test_scan_archives_opens_wheel_and_sdist_contents(tmp_path):
    """아카이브 **안쪽**까지 푼다 — 파일명만 봐서는 유출을 못 잡는다."""
    _write_wheel(tmp_path / "p-0.0.0-py3-none-any.whl", f"leak {FAKE[0]} here")
    _write_sdist(tmp_path / "p-0.0.0.tar.gz", f"leak {FAKE[1]} here", tmp_path)

    hits, count = scan.scan_archives(tmp_path, FAKE)

    assert count == 2, "wheel·sdist 둘 다 검사해야 한다"
    assert sorted(index for _, index in hits) == [0, 1]
    assert {where.split(":")[0] for where, _ in hits} == {
        "p-0.0.0-py3-none-any.whl", "p-0.0.0.tar.gz",
    }


def test_clean_archives_produce_no_hits(tmp_path):
    """깨끗한 산출물에는 히트가 없어야 한다(거짓 양성 방지)."""
    _write_wheel(tmp_path / "p-0.0.0-py3-none-any.whl", "아무 문제 없는 내용")
    _write_sdist(tmp_path / "p-0.0.0.tar.gz", "아무 문제 없는 내용", tmp_path)

    hits, count = scan.scan_archives(tmp_path, FAKE)

    assert count == 2
    assert hits == []


def test_missing_denylist_fails_closed(tmp_path, monkeypatch):
    """🔴 denylist를 못 읽으면 통과가 아니라 실패(exit 2)여야 한다.

    여기서 0을 돌려주면 denylist 파일을 지운 것만으로 모든 배포가 "CLEAN"이 된다.
    조용히 생략된 스캔은 통과한 것처럼 보여서 가장 위험하다.
    """
    monkeypatch.setattr(scan, "DENYLIST", tmp_path / "does-not-exist")
    assert scan.main(["--no-dist"]) == 2


def test_empty_denylist_also_fails_closed(tmp_path, monkeypatch):
    """주석만 있고 토큰이 하나도 없는 denylist도 '못 읽은 것'으로 친다."""
    empty = tmp_path / "empty-tokens"
    empty.write_text("# 주석만 있다\n\n", encoding="utf-8")
    monkeypatch.setattr(scan, "DENYLIST", empty)
    assert scan.main(["--no-dist"]) == 2


def test_missing_dist_directory_fails_closed(tmp_path, monkeypatch):
    """dist가 없는데 '깨끗하다'고 하면 안 된다 — 빌드를 안 한 것이다."""
    tokens = tmp_path / "tokens"
    tokens.write_text("\n".join(FAKE) + "\n", encoding="utf-8")
    monkeypatch.setattr(scan, "DENYLIST", tokens)
    assert scan.main(["--dist-only", "--dist", str(tmp_path / "no-such-dir")]) == 2


def test_empty_dist_directory_fails_closed(tmp_path, monkeypatch):
    """디렉터리는 있는데 아카이브가 0개인 경우도 실패다(빈 루프 통과 방지)."""
    tokens = tmp_path / "tokens"
    tokens.write_text("\n".join(FAKE) + "\n", encoding="utf-8")
    empty_dist = tmp_path / "dist"
    empty_dist.mkdir()
    monkeypatch.setattr(scan, "DENYLIST", tokens)
    assert scan.main(["--dist-only", "--dist", str(empty_dist)]) == 2


def test_leak_in_dist_returns_failure(tmp_path, monkeypatch):
    """심은 토큰이 있으면 exit 1."""
    tokens = tmp_path / "tokens"
    tokens.write_text("\n".join(FAKE) + "\n", encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    _write_wheel(dist / "p-0.0.0-py3-none-any.whl", f"leak {FAKE[0]}")
    _write_sdist(dist / "p-0.0.0.tar.gz", "clean", tmp_path)
    monkeypatch.setattr(scan, "DENYLIST", tokens)

    assert scan.main(["--dist-only", "--dist", str(dist)]) == 1


def test_tracked_files_enumerates_instead_of_hardcoding():
    """추적 파일은 git에서 열거한다 — 손으로 적은 목록은 조용히 낡는다."""
    files = scan.tracked_files()
    names = {p.name for p in files}

    assert files, "추적 파일이 0개 — 열거가 헛돌고 있다"
    # 하드코딩 목록이었다면 빠졌을 파일들(목록 작성 후에 생겼다).
    for later_addition in ("verify_dist.py", "server.py", "test_docs_consistency.py"):
        assert later_addition in names, f"{later_addition}이 검사 대상에서 빠졌다"


def test_load_tokens_skips_comments_and_blanks(tmp_path):
    """denylist 파싱 — 주석·빈 줄은 토큰이 아니다."""
    f = tmp_path / "tokens"
    f.write_text("# 설명\n\n  alpha  \nbeta\n# 꼬리 주석\n", encoding="utf-8")
    assert scan.load_tokens(f) == ("alpha", "beta")
