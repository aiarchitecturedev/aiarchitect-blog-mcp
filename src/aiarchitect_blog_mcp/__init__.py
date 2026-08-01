"""AI아키텍트 블로그 MCP 서버.

aiarchitect.tistory.com 의 공개 기술 글을 AI 에이전트가 검색·열람할 수 있도록
MCP(Model Context Protocol) 도구로 노출한다.
"""

def main() -> None:
    """콘솔 진입점: stdio 전송으로 MCP 서버를 실행한다."""
    from .server import mcp  # 지연 임포트: corpus/빌드 도구는 fastmcp 없이도 임포트 가능

    mcp.run()


__all__ = ["main"]
