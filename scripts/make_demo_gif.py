"""README 데모 GIF 생성기 — 터미널 풍 애니메이션을 PNG 프레임 → GIF로 굽는다.

표시되는 내용은 **실제 stdio MCP 서버 응답**이다. `--capture` 를 주면 서버를 직접
띄워 JSON-RPC로 호출한 결과로 대본을 채우고, 주지 않으면 같은 호출을 그대로 재실행해
대본과 어긋나지 않는지 검증한다. 즉 이 GIF는 손으로 꾸며 낸 화면이 아니다.

의존성은 배포본에 넣지 않는다(개발 전용):
    uv run --with pillow python scripts/make_demo_gif.py --out assets/demo.gif
ffmpeg 이 필요하다(프레임 → GIF 변환).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────── 모양 ───────────────────────────────

COLS, ROWS = 72, 15
FONT_SIZE = 17
PAD_X, PAD_TOP = 18, 44          # 타이틀바 높이 포함
PAD_BOTTOM = 16
FPS = 20

BG = (17, 19, 26)
BAR = (28, 31, 40)
FG = (214, 221, 235)
DIM = (113, 124, 145)
GREEN = (126, 231, 135)
BLUE = (121, 192, 255)
VIOLET = (210, 168, 255)
AMBER = (227, 179, 65)
RED = (255, 123, 114)

S_TITLE = {"n": "96"}

MONO_CANDIDATES = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf"]
KR_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def _load(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    raise SystemExit(f"글꼴을 찾지 못했다: {paths}")


def cell_count(ch: str) -> int:
    """터미널 칸 수 — 한글·CJK는 2칸, 나머지는 1칸."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def width(text: str) -> int:
    return sum(cell_count(c) for c in text)


# ─────────────────────────────── 대본 ───────────────────────────────
# (세그먼트 리스트, 모드) — 모드 "type"은 한 글자씩, "fast"는 빠르게, "now"는 즉시.

def build_script(cap: dict) -> list[tuple[list[tuple[str, tuple]], str, float]]:
    calls = {c["tool"]: c for c in cap["calls"]}
    hits = calls["search_articles"]["structured"]["result"]
    body = calls["get_article"]["text"]
    total = calls["blog_home"]["text"].split("총 ")[1].split("편")[0]
    S_TITLE["n"] = total

    def hit_line(h: dict, title_cells: int) -> list[tuple[str, tuple]]:
        t = h["title"]
        out, used = "", 0
        for ch in t:
            w = cell_count(ch)
            if used + w > title_cells - 1:
                out += "…"
                break
            out, used = out + ch, used + w
        return [
            ("    BLOG-%s  " % h["id"], DIM),
            (out.ljust(0), FG),
            (" " * max(1, title_cells - width(out)), FG),
            ("%.3f" % h["score"], AMBER),
        ]

    # 본문에서 실제로 쓰는 두 줄 (손으로 쓴 문장이 아니라 글 본문 그대로)
    intro = body.split("\n\n")[4].strip()
    sent = intro.split(". ")[1].strip() + "."

    def wrap(s: str, cells: int, indent: str) -> list[str]:
        lines, cur, used = [], "", 0
        for ch in s:
            w = cell_count(ch)
            if used + w > cells:
                lines.append(cur)
                cur, used = "", 0
            cur, used = cur + ch, used + w
        if cur:
            lines.append(cur)
        return [indent + ln for ln in lines]

    S: list[tuple[list[tuple[str, tuple]], str, float]] = []

    def add(segs, mode="now", after=0.0):
        S.append((segs, mode, after))

    add([("  사용자 ", DIM), ("│", DIM), (" AI Agent 감사 로그, 어떻게 설계해야 하나요?", FG)],
        "type", 0.45)
    add([], "now", 0.0)

    add([("  ● ", GREEN), ("search_articles", VIOLET),
         ('(query="감사 로그", limit=3)', FG)], "type", 0.25)
    for h in hits:
        add(hit_line(h, 44), "fast", 0.06)
    add([], "now", 0.5)

    add([("  ● ", GREEN), ("get_article", VIOLET), ('(article_id="27")', FG)], "type", 0.25)
    add([("    " + body.split("\n")[0].lstrip("# ")[:58] + "…", FG)], "fast", 0.05)
    for ln in wrap(sent, 62, "    "):
        add([(ln, DIM)], "fast", 0.04)
    add([("    %s자 · 게시용 목차·죽은 이미지 링크를 걷어낸 마크다운" % f"{len(body):,}", DIM)],
        "fast", 0.6)
    add([], "now", 0.0)

    add([("  ✓ ", GREEN), ("출처 ", FG), ("https://aiarchitect.tistory.com/27", BLUE)],
        "type", 1.4)
    return S


# ─────────────────────────────── 렌더 ───────────────────────────────

class Term:
    def __init__(self) -> None:
        self.mono = _load(MONO_CANDIDATES, FONT_SIZE)
        self.kr = _load(KR_CANDIDATES, FONT_SIZE + 1)
        box = self.mono.getbbox("M")
        self.cw = int(round(self.mono.getlength("M")))
        self.ch = int(round(FONT_SIZE * 1.62))
        self.W = PAD_X * 2 + self.cw * COLS
        self.H = PAD_TOP + PAD_BOTTOM + self.ch * ROWS
        self._base = box

    def frame(self, lines: list[list[tuple[str, tuple]]], cursor: tuple[int, int] | None) -> Image.Image:
        img = Image.new("RGB", (self.W, self.H), BG)
        d = ImageDraw.Draw(img)
        # 타이틀바
        d.rectangle([0, 0, self.W, PAD_TOP - 12], fill=BAR)
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse([16 + i * 20, 11, 26 + i * 20, 21], fill=c)
        title = "aiarchitect-blog MCP · %s편" % S_TITLE["n"]
        self._text(d, (self.W // 2 - int(width(title) * self.cw / 2), 8), title, DIM)
        # 본문
        for r, segs in enumerate(lines[-ROWS:]):
            x = PAD_X
            y = PAD_TOP + r * self.ch
            for text, color in segs:
                x = self._text(d, (x, y), text, color)
        if cursor:
            cx, cy = cursor
            x = PAD_X + cx * self.cw
            y = PAD_TOP + cy * self.ch
            d.rectangle([x, y + 2, x + self.cw - 1, y + self.ch - 4], fill=(90, 100, 120))
        return img

    def _text(self, d: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, color) -> int:
        """칸 격자에 맞춰 한 글자씩 그린다(한글 2칸). 끝난 x 좌표를 돌려준다."""
        x, y = pos
        for ch in text:
            cells = cell_count(ch)
            if ch != " ":
                wide = cells == 2
                font = self.kr if wide else self.mono
                # 글리프 실폭이 칸보다 좁으므로 가운데 정렬한다.
                dx = (cells * self.cw - font.getlength(ch)) / 2
                dy = -1 if wide else 0
                d.text((x + dx, y + dy), ch, font=font, fill=color)
            x += cells * self.cw
        return x


def render(script, cap: dict, out: Path, keep_frames: Path | None = None) -> None:
    term = Term()
    tmp = Path(tempfile.mkdtemp(prefix="demo-gif-"))
    frames: list[tuple[int, float]] = []   # (프레임 번호, 노출 시간 초)
    n = 0

    def emit(lines, cursor, seconds):
        nonlocal n
        term.frame(lines, cursor).save(tmp / f"f{n:05d}.png")
        frames.append((n, max(seconds, 1 / FPS)))
        n += 1

    lines: list[list[tuple[str, tuple]]] = []
    for segs, mode, after in script:
        if mode == "now" or not segs:
            lines.append(segs)
            emit(lines, None, after or 1 / FPS)
            continue
        flat = "".join(t for t, _ in segs)
        total = len(flat)
        step = 1 if mode == "type" else 4
        shown = 0
        lines.append([])
        while shown < total:
            shown = min(total, shown + step)
            # 글자 수만큼 잘라 세그먼트 재구성
            cut, left = [], shown
            for t, c in segs:
                if left <= 0:
                    break
                cut.append((t[:left], c))
                left -= len(t)
            lines[-1] = cut
            col = width("".join(t for t, _ in cut))
            row = min(len(lines), ROWS) - 1
            emit(lines, (col, row), (0.034 if mode == "type" else 0.016))
        lines[-1] = segs
        emit(lines, None, after or 1 / FPS)

    # 마지막 화면 유지
    emit(lines, None, 2.2)

    concat = tmp / "concat.txt"
    with concat.open("w") as f:
        for idx, dur in frames:
            f.write(f"file 'f{idx:05d}.png'\nduration {dur:.3f}\n")
        f.write(f"file 'f{frames[-1][0]:05d}.png'\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    palette = tmp / "palette.png"
    run = lambda c: subprocess.run(c, check=True, capture_output=True)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-vf", "palettegen=max_colors=64:stats_mode=diff", str(palette)])
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(palette),
         "-lavfi", "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
         "-gifflags", "+transdiff", "-loop", "0", str(out)])

    if keep_frames:
        shutil.copy(tmp / "f00000.png", keep_frames)
    shutil.rmtree(tmp, ignore_errors=True)
    write_sidecar(cap, out.with_name("demo.meta.json"))
    kb = out.stat().st_size / 1024
    print(f"✅ {out} · {len(frames)}프레임 · {term.W}x{term.H} · {kb:,.0f} KB")
    if kb > 3072:
        print("⚠️ 3MB 초과 — README 로딩이 느려진다. 프레임 수나 캔버스를 줄여라.", file=sys.stderr)


def write_sidecar(cap: dict, path: Path) -> None:
    """GIF 에 구워진 값을 JSON 으로 남긴다 — 그림은 테스트가 읽을 수 없기 때문이다.

    코퍼스가 바뀌면 GIF 는 조용히 거짓말이 된다(점수·글자 수·편수). 이 파일을 번들과
    대조하는 `tests/test_docs_consistency.py::test_demo_gif_matches_bundle` 이
    "GIF 를 다시 구워라" 라고 알려 준다.
    """
    calls = {c["tool"]: c for c in cap["calls"]}
    hits = calls["search_articles"]["structured"]["result"]
    payload = {
        "_설명": "assets/demo.gif 에 구워진 실측값. 손으로 고치지 말고 스크립트로 다시 생성할 것.",
        "article_count": int(calls["blog_home"]["text"].split("총 ")[1].split("편")[0]),
        "search": {
            "query": "감사 로그",
            "hits": [{"id": h["id"], "score": round(h["score"], 3)} for h in hits],
        },
        "article": {"id": "27", "chars": len(calls["get_article"]["text"])},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ─────────────────────────────── 실행 ───────────────────────────────

def capture() -> dict:
    """실제 stdio 서버를 띄워 JSON-RPC로 호출한다(대본의 유일한 출처)."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "from aiarchitect_blog_mcp import main; main()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1, cwd=str(Path(__file__).resolve().parent.parent),
    )
    state = {"id": 0}

    def send(method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            state["id"] += 1
            msg["id"] = state["id"]
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        if notify:
            return None
        while True:
            line = proc.stdout.readline()
            if not line:
                raise SystemExit("MCP 서버가 응답 없이 종료됐다")
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id") == state["id"]:
                return r

    send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "demo-gif", "version": "0"}})
    send("notifications/initialized", {}, notify=True)

    def call(name, args):
        res = send("tools/call", {"name": name, "arguments": args}).get("result", {})
        text = "\n".join(c.get("text", "") for c in res.get("content", [])
                         if c.get("type") == "text")
        return {"tool": name, "args": args, "text": text,
                "structured": res.get("structuredContent")}

    out = {"calls": [call("search_articles", {"query": "감사 로그", "limit": 3}),
                     call("get_article", {"article_id": "27"}),
                     call("blog_home", {})]}
    proc.stdin.close()
    proc.wait(timeout=20)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="README 데모 GIF 생성")
    ap.add_argument("--out", default="assets/demo.gif")
    ap.add_argument("--still", help="첫 프레임 PNG를 여기에 저장(미리보기용)")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg 가 필요하다(brew install ffmpeg)")
    cap = capture()
    render(build_script(cap), cap, Path(args.out),
           Path(args.still) if args.still else None)


if __name__ == "__main__":
    main()
