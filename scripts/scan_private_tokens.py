#!/usr/bin/env python3
"""익명성 denylist 스캔 — 배포 산출물·추적 소스·번들 데이터에 개인 식별자가 없는지 검사.

**왜 별도 스크립트인가.** denylist(`.private-tokens`)는 비추적 로컬 파일이라 GitHub
러너가 읽을 수 없다. 그래서 이 검사만 CI에 없고 배포 직전 **수동 단계**로 남아 있다
(`PUBLISHING.md` §2-3). 수동으로 남을수록 재현 가능해야 해서 스크립트로 둔다 —
토큰 내용은 여전히 비추적 파일에만 있고, 이 파일에는 리터럴이 하나도 없다.

🔴 **fail-closed**: denylist를 못 읽으면 "깨끗하다"가 아니라 **실패**(exit 2)다.
`build_index.py`는 경고만 하고 지나가고(콘텐츠 빌드를 막지 않으려고), 테스트는 skip한다.
배포 게이트에서는 **조용히 생략된 스캔이 가장 위험하다** — 통과한 것처럼 보이기 때문이다.

검사 대상(기본값은 셋 다):
  1. `dist/`의 wheel·sdist — 아카이브 **안쪽**까지 푼다. 실제로 배포되는 바이트다.
  2. git이 추적하는 모든 파일 — `git ls-files`로 **열거**한다. 손으로 적은 목록은
     파일이 늘 때 조용히 낡는다(실제로 그랬다 — 아래 `tracked` 주석 참조).
  3. 번들 데이터(`data/articles_index.json`, `data/articles/*.md`) — 2에 포함되지만
     소스 트리만 검사하고 싶을 때를 위해 따로 둔다.

사용:
    python scripts/scan_private_tokens.py              # 전부
    python scripts/scan_private_tokens.py --dist-only  # 배포 산출물만
    python scripts/scan_private_tokens.py --no-dist    # 소스 트리만(dist 빌드 전)

종료 코드: 0 깨끗함 · 1 유출 발견 · 2 denylist를 읽을 수 없음(fail-closed)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / ".private-tokens"
# 아카이브 안에서 텍스트로 열어 볼 확장자. 그 외(바이너리)는 decode 오류를 무시하고 훑는다.
_SKIP_SUFFIXES = {".pyc", ".so", ".dylib", ".whl", ".tar", ".gz", ".zip", ".png", ".jpg", ".gif"}


def load_tokens(path: Path) -> tuple[str, ...]:
    """비추적 denylist에서 소문자 토큰을 읽는다. 주석(`#`)과 빈 줄은 건너뛴다."""
    if not path.exists():
        return ()
    tokens = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            tokens.append(s.lower())
    return tuple(tokens)


def find_in_text(text: str, tokens: tuple[str, ...]) -> list[int]:
    """텍스트에 들어 있는 denylist 토큰의 **인덱스**(0-based, 소문자 비교).

    토큰 문자열이 아니라 인덱스를 돌려준다. 익명성 도구가 제 입으로 토큰을 흘리면
    안 되기 때문이다 — 일부만 가려도 `/U…n/`처럼 형태가 드러난다. 유지관리자는
    번호로 자기 로컬 denylist를 찾아보면 된다.
    """
    lowered = text.lower()
    return [i for i, t in enumerate(tokens) if t in lowered]


def tracked_files(root: Path = ROOT) -> list[Path]:
    """git이 추적하는 모든 파일.

    ⚠️ 손으로 적은 목록을 쓰지 않는 이유: `tests/test_corpus.py`의 회귀 테스트가
    대상 파일 5개를 하드코딩해 두는 바람에, 그 뒤에 생긴 `verify_dist.py`·
    `server.py`·`test_docs_consistency.py` 등이 검사 밖에 있었다. 열거가 답이다.
    """
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [root / name for name in out.split("\0") if name]


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() in _SKIP_SUFFIXES or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def scan_files(paths: list[Path], tokens: tuple[str, ...]) -> list[tuple[str, int]]:
    """일반 파일들을 훑어 (위치, denylist 인덱스) 쌍을 돌려준다."""
    hits = []
    for p in paths:
        text = _read_text(p)
        if text is None:
            continue
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        hits += [(str(rel), i) for i in find_in_text(text, tokens)]
    return hits


def scan_archives(dist_dir: Path, tokens: tuple[str, ...]) -> tuple[list[tuple[str, int]], int]:
    """wheel·sdist 안쪽까지 풀어 훑는다. (히트, 검사한 아카이브 수)를 돌려준다."""
    hits: list[tuple[str, int]] = []
    archives = sorted(dist_dir.glob("*.whl")) + sorted(dist_dir.glob("*.tar.gz"))

    for archive in archives:
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as zf:
                for name in zf.namelist():
                    body = zf.read(name).decode("utf-8", "ignore")
                    hits += [(f"{archive.name}:{name}", i) for i in find_in_text(body, tokens)]
        else:
            with tarfile.open(archive) as tf:
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    body = extracted.read().decode("utf-8", "ignore")
                    hits += [(f"{archive.name}:{member.name}", i) for i in find_in_text(body, tokens)]
    return hits, len(archives)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="익명성 denylist 스캔(fail-closed)")
    parser.add_argument("--dist", default="dist", help="배포 산출물 디렉터리(기본 dist/)")
    parser.add_argument("--dist-only", action="store_true", help="배포 산출물만 검사")
    parser.add_argument("--no-dist", action="store_true", help="소스 트리만 검사")
    parser.add_argument(
        "--denylist",
        help="denylist 파일 경로(기본: 저장소 루트의 .private-tokens). "
             "CI가 Secret에서 쓴 임시 파일을 가리킬 때 쓴다.",
    )
    args = parser.parse_args(argv)

    # 🔴 모듈 상수를 **호출 시점에** 읽는다. 기본 인자(`path=DENYLIST`)로 받으면
    # 정의 시점에 묶여서 바깥에서 바꿀 수 없다 — 테스트가 이 결함을 잡아냈다.
    denylist_path = Path(args.denylist) if args.denylist else DENYLIST
    tokens = load_tokens(denylist_path)
    if not tokens:
        # 🔴 여기서 0을 돌려주면 denylist를 지운 것만으로 모든 배포가 "CLEAN"이 된다.
        print(
            f"❌ denylist를 읽을 수 없음: {denylist_path}\n"
            "   스캔을 생략하지 않고 실패로 처리한다(fail-closed). "
            "유지관리자는 비추적 정책 파일을 준비하세요.",
            file=sys.stderr,
        )
        return 2

    hits: list[tuple[str, int]] = []
    scanned: list[str] = []

    if not args.dist_only:
        files = tracked_files()
        hits += scan_files(files, tokens)
        scanned.append(f"추적 파일 {len(files)}개")

    if not args.no_dist:
        dist_dir = Path(args.dist)
        if not dist_dir.is_dir():
            print(f"❌ 배포 디렉터리 없음: {dist_dir} — 먼저 `uv build`", file=sys.stderr)
            return 2
        archive_hits, count = scan_archives(dist_dir, tokens)
        if count == 0:
            print(f"❌ {dist_dir}에 wheel·sdist가 없음 — 먼저 `uv build`", file=sys.stderr)
            return 2
        hits += archive_hits
        scanned.append(f"아카이브 {count}개")

    if hits:
        print(f"❌ 비공개 식별자 유출 {len(hits)}건:", file=sys.stderr)
        for where, index in hits:
            # 토큰 내용은 찍지 않는다 — 번호만 준다(위 find_in_text 주석 참조).
            print(f"   {where}  ← denylist {index + 1}번째 항목", file=sys.stderr)
        return 1

    print(f"✅ CLEAN — {', '.join(scanned)} 검사, denylist {len(tokens)}개 토큰")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
