"""문서에 적힌 수치 ↔ 실제 번들 대조(drift 가드).

편수·분류 수·도구 수가 README와 pyproject에 **손으로 적혀 있다**. 코퍼스를 갱신하면
번들만 바뀌고 문서는 그대로 남는다. v0.1.2(69→94편)에서도 README 두 곳과 pyproject를
손으로 고쳤는데, 하나라도 빠뜨렸다면 아무것도 잡아주지 않았을 것이다.

각 테스트는 **패턴을 하나도 못 찾으면 실패**한다. 문구가 바뀌어 정규식이 헛돌면
검사를 통과한 것처럼 보이는 것이 가장 위험하기 때문이다.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from aiarchitect_blog_mcp.corpus import DATA_DIR, Corpus

ROOT = Path(__file__).parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _bundled_count() -> int:
    index = json.loads((DATA_DIR / "articles_index.json").read_text(encoding="utf-8"))
    return index["count"]


def _found(pattern: str, text: str) -> list[int]:
    return [int(m) for m in re.findall(pattern, text)]


def test_readme_article_count_matches_bundle():
    counts = _found(r"(\d+)편", README)
    assert counts, "README에서 `N편` 표기를 찾지 못했다 — 정규식이 헛돌고 있다"
    assert set(counts) == {_bundled_count()}, (
        f"README 편수 {sorted(set(counts))} != 번들 {_bundled_count()}편"
    )


def test_pyproject_description_count_matches_bundle():
    counts = _found(r"(\d+) articles", PYPROJECT)
    assert counts, "pyproject에서 `N articles` 표기를 찾지 못했다"
    assert set(counts) == {_bundled_count()}, (
        f"pyproject 편수 {sorted(set(counts))} != 번들 {_bundled_count()}편"
    )


def test_readme_category_count_matches_corpus():
    counts = _found(r"\((\d+)종\)", README)
    assert counts, "README에서 `(N종)` 표기를 찾지 못했다"
    actual = len(Corpus().categories())
    assert set(counts) == {actual}, f"README 분류 수 {sorted(set(counts))} != 실제 {actual}종"


def test_readme_tool_count_matches_server():
    counts = _found(r"(\d+)개 도구", README)
    assert counts, "README에서 `N개 도구` 표기를 찾지 못했다"
    actual = len(asyncio.run(_list_tools()))
    assert set(counts) == {actual}, f"README 도구 수 {sorted(set(counts))} != 실제 {actual}개"


async def _list_tools():
    from aiarchitect_blog_mcp.server import mcp

    return await mcp.list_tools()


DEMO_GIF = ROOT / "assets" / "demo.gif"
DEMO_META = ROOT / "assets" / "demo.meta.json"


def test_demo_gif_matches_bundle():
    """README 데모 GIF ↔ 번들 대조.

    GIF는 **실제 서버 응답을 구운 그림**이라, 코퍼스가 바뀌면 화면의 편수·점수·글자 수가
    조용히 거짓이 된다. 그림은 어떤 테스트도 읽을 수 없으므로, 구울 때 함께 남긴
    `demo.meta.json`을 번들과 대조한다. 실패하면 값을 손으로 고치지 말고 다시 굽는다:

        uv run --with pillow python scripts/make_demo_gif.py
    """
    assert DEMO_GIF.exists(), "assets/demo.gif 이 없다 — scripts/make_demo_gif.py 로 생성할 것"
    assert DEMO_META.exists(), (
        "assets/demo.meta.json 이 없다 — GIF만 있고 구워진 값의 기록이 없으면 대조할 수 없다"
    )
    meta = json.loads(DEMO_META.read_text(encoding="utf-8"))

    assert meta["article_count"] == _bundled_count(), (
        f"GIF 타이틀바 {meta['article_count']}편 != 번들 {_bundled_count()}편 — GIF를 다시 구워라"
    )

    corpus = Corpus()
    expected_hits = meta["search"]["hits"]
    hits = corpus.search(meta["search"]["query"], limit=len(expected_hits))
    actual = [{"id": h["id"], "score": round(h["score"], 3)} for h in hits]
    assert actual == expected_hits, (
        f"GIF의 검색 결과가 지금 코퍼스와 다르다({actual} != {expected_hits}) — GIF를 다시 구워라"
    )

    chars = len(corpus.render_article(meta["article"]["id"]))
    assert chars == meta["article"]["chars"], (
        f"GIF의 본문 글자 수 {meta['article']['chars']:,} != 지금 {chars:,} — GIF를 다시 구워라"
    )


SERVER_JSON = ROOT / "server.json"


def _server_json() -> dict:
    return json.loads(SERVER_JSON.read_text(encoding="utf-8"))


def test_server_json_version_matches_pyproject():
    """공식 MCP Registry에 올리는 버전 ↔ 실제 패키지 버전.

    릴리스 워크플로는 `server.json`을 **덮어쓰지 않는다**(저장소가 정본). 그래서 버전을
    따로 올리는 것을 잊으면 PyPI에는 새 버전이, 레지스트리에는 옛 버전이 남는다.
    """
    meta = _server_json()
    version = re.search(r'^version = "([^"]+)"', PYPROJECT, re.M)
    assert version, "pyproject에서 version 을 찾지 못했다"
    expected = version.group(1)
    assert meta["version"] == expected, (
        f"server.json version {meta['version']} != pyproject {expected}"
    )
    pkgs = meta["packages"]
    assert len(pkgs) == 1, f"packages가 1개라고 가정했는데 {len(pkgs)}개다"
    assert pkgs[0]["version"] == expected, (
        f"server.json packages[0].version {pkgs[0]['version']} != pyproject {expected}"
    )


def test_server_json_package_identifier_matches_pyproject():
    pkg = _server_json()["packages"][0]
    name = re.search(r'^name = "([^"]+)"', PYPROJECT, re.M)
    assert name, "pyproject에서 name 을 찾지 못했다"
    assert pkg["registryType"] == "pypi", f"registryType이 pypi가 아니다: {pkg['registryType']}"
    assert pkg["identifier"] == name.group(1), (
        f"server.json identifier {pkg['identifier']} != pyproject name {name.group(1)}"
    )


def test_readme_carries_mcp_name_marker():
    """README의 `mcp-name:` 표식 ↔ server.json 의 name.

    레지스트리는 **PyPI에 올라간 패키지 설명(=이 README)** 에서 이 표식을 찾아 소유권을
    확인한다. 표식이 없거나 이름이 어긋나면 게시가 "Package validation failed"로 떨어진다.
    이 테스트가 실패하면 README를 고치고 **새 버전을 PyPI에 올려야** 한다 — 이미 올라간
    버전의 설명은 바꿀 수 없기 때문이다.
    """
    name = _server_json()["name"]
    marker = f"mcp-name: {name}"
    assert marker in README, f"README에서 `{marker}` 를 찾지 못했다"
    # 표식 뒤에는 경계(공백·개행·주석 닫기)가 와야 한다. 문장부호에 붙이면 매칭되지 않는다.
    after = README.split(marker, 1)[1][:1]
    assert after in ("", " ", "\n", "\t"), (
        f"`{marker}` 바로 뒤에 {after!r} 가 붙어 있다 — 경계가 없으면 레지스트리가 못 읽는다"
    )
