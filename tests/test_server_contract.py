"""서버가 외부에 내보이는 계약 검사 — 읽기 전용 선언(annotations).

README는 **"5개 도구 모두 `readOnlyHint`가 선언돼 있다"**고 보증한다. 그런데 이 보증을
확인하는 장치가 없었다. `test_docs_consistency.py`는 도구 **개수**만 센다 — 여섯 번째
도구를 annotation 없이 추가하고 README를 "6개 도구"로 고치면 개수는 맞으니 통과한다.
읽기 전용은 이 서버가 내세우는 보안 성질이라, 개수가 아니라 **선언 자체**를 봐야 한다.

검사는 하드코딩한 도구 이름 목록이 아니라 `list_tools()`가 실제로 내보내는 집합 전체를
훑는다. 새 도구는 **등록되는 순간 자동으로 검사 대상**이 된다.
"""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP

# MCP 읽기 전용 계약: 읽기만 함 · 같은 입력은 같은 결과 · 외부 세계를 건드리지 않음.
# (destructiveHint는 readOnlyHint가 True면 의미가 없어 선언하지 않는다 — MCP 사양)
EXPECTED = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}


def _violations(tools) -> list[str]:
    """읽기 전용 선언이 빠졌거나 값이 다른 도구의 이름.

    annotations 자체가 없는 경우(`@mcp.tool()`을 맨손으로 붙인 경우)도 위반으로 잡는다.
    """
    bad = []
    for tool in tools:
        annotations = getattr(tool, "annotations", None)
        if annotations is None:
            bad.append(tool.name)
            continue
        actual = {key: getattr(annotations, key, None) for key in EXPECTED}
        if actual != EXPECTED:
            bad.append(tool.name)
    return bad


def _list_tools(server: FastMCP):
    return asyncio.run(server.list_tools())


def test_every_exposed_tool_declares_read_only_annotations():
    """노출되는 모든 도구가 읽기 전용을 선언해야 한다(새 도구도 자동 포함)."""
    from aiarchitect_blog_mcp.server import mcp

    tools = _list_tools(mcp)
    # 빈 목록에 대고 루프를 돌면 아무것도 검사하지 않고 통과한다 — 먼저 막는다.
    assert tools, "노출된 도구가 0개 — 검사가 헛돌고 있다"
    assert _violations(tools) == [], (
        f"읽기 전용 선언이 빠진 도구: {_violations(tools)} (기대: {EXPECTED})"
    )


def test_the_guard_actually_rejects_a_tool_without_annotations():
    """절제 실험 — 선언을 빼면 위 검사가 실제로 잡는가.

    이 저장소에서 한 번 덴 적이 있다: BM25 랭킹 테스트의 초안은 검사 대상 기능을
    제거해도 그대로 통과했다. 그 뒤로는 가드마다 '빼면 실제로 걸리는지'를 같이 둔다.
    """
    probe = FastMCP(name="probe")

    @probe.tool(annotations=dict(EXPECTED))
    def annotated() -> str:
        """읽기 전용을 선언한 도구."""
        return "ok"

    @probe.tool()
    def bare() -> str:
        """선언을 빼먹은 도구 — 잡혀야 한다."""
        return "ok"

    assert _violations(_list_tools(probe)) == ["bare"]


def test_the_guard_rejects_a_tool_that_claims_to_write():
    """절제 실험 — 값이 틀린 경우(읽기 전용이 아니라고 선언)도 잡아야 한다."""
    probe = FastMCP(name="probe-write")

    @probe.tool(annotations={**EXPECTED, "readOnlyHint": False})
    def writes() -> str:
        """쓰기 도구로 선언된 도구 — 잡혀야 한다."""
        return "ok"

    assert _violations(_list_tools(probe)) == ["writes"]
