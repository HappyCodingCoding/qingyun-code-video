#!/usr/bin/env python3
"""Check the tools this skill needs and say how to install what is missing.

  check_env.py                          # web-page rendering and audio synthesis (step 0)
  check_env.py --only remotion manim    # only what these extras need: remotion, hyperframes, manim, yt-dlp
"""
import argparse, importlib.util, shutil, subprocess, sys

EXTRAS = ("remotion", "hyperframes", "manim", "yt-dlp")
ok = True


def report(name, good, fix=""):
    global ok
    ok &= good
    print(f"[{'ok' if good else 'missing'}] {name}" + ("" if good else f"  ->  {fix}"))


def check_doubao():
    """Default voiceover engine: credentials present and accepted (a WebSocket handshake, nothing synthesized)."""
    has_http = importlib.util.find_spec("aiohttp") is not None
    report("aiohttp (Doubao TTS)", has_http, "python3 -m pip install aiohttp")
    if not has_http or importlib.util.find_spec("numpy") is None:
        return
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from audio_tools import VOLC_NO_AUTH, volc_auths, volc_connect   # same credentials and connection the tts command uses
    auths = volc_auths()
    report("Doubao TTS credentials", bool(auths), VOLC_NO_AUTH)
    if not auths:
        return
    import aiohttp, asyncio

    async def handshake(headers):
        async with aiohttp.ClientSession() as http, volc_connect(http, {**headers, "X-Api-Resource-Id": "seed-tts-2.0"}):
            pass
    accepted, problems = None, []
    for name, headers in auths:   # the same order the tts command tries them in
        try:
            asyncio.run(asyncio.wait_for(handshake(headers), timeout=20)); accepted = name; break
        except aiohttp.WSServerHandshakeError as e:
            ark = ", an ark- key is a 火山方舟 key" if headers.get("X-Api-Key", "").startswith("ark-") else ""
            problems.append(f"{name}: HTTP {e.status}, invalid or seed-tts-2.0 not enabled{ark}")
        except Exception as e:
            problems.append(f"{name}: {type(e).__name__}, check the network or proxy")
    for p in problems if accepted else []:
        print(f"[info] Doubao TTS refused the {p}")
    report(f"Doubao TTS accepts the {accepted or 'credentials'}", bool(accepted), "; ".join(problems))


def check_base():
    report("python3 >= 3.9", sys.version_info >= (3, 9), "install Python 3.9+")
    has_ff = bool(shutil.which("ffmpeg"))
    report("ffmpeg", has_ff, "macOS: brew install ffmpeg | Windows: winget install ffmpeg | Linux: apt install ffmpeg")
    report("ffprobe", bool(shutil.which("ffprobe")), "comes with ffmpeg")
    report("numpy (audio synthesis)", importlib.util.find_spec("numpy") is not None, "python3 -m pip install numpy")
    check_doubao()
    tts_ok = False
    if importlib.util.find_spec("edge_tts") is not None:   # audio_tools.py tts needs the boundary option (edge-tts 7+)
        import edge_tts, inspect
        tts_ok = "boundary" in inspect.signature(edge_tts.Communicate).parameters
    report("edge-tts 7+ (voiceover fallback)", tts_ok, "python3 -m pip install -U edge-tts")
    if tts_ok:   # Microsoft refuses outdated clients with HTTP 403, so a version check alone is not enough
        import asyncio

        async def probe():
            stream = edge_tts.Communicate("测试", "zh-CN-XiaoxiaoNeural").stream()
            try:
                async for c in stream:
                    if c["type"] == "audio":
                        return
            finally:   # close the stream so its HTTP session does not leak ("Unclosed client session")
                await stream.aclose()
        try:
            asyncio.run(asyncio.wait_for(probe(), timeout=20)); live = True
        except Exception:
            live = False
        report("edge-tts reaches Microsoft's service", live,
               "python3 -m pip install -U edge-tts (a 403 means the client is too old); otherwise check the network or proxy")
    has_pw = importlib.util.find_spec("playwright") is not None
    report("playwright (python)", has_pw, "python3 -m pip install playwright")

    if has_pw:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
        from render import BROWSERS, GPU_ARGS, has_webgl2   # same browsers and flags the renderer uses
        from playwright.sync_api import sync_playwright
        launched, webgl = [], []
        with sync_playwright() as p:
            for kw in BROWSERS:
                name = kw.get("channel", "playwright chromium")
                try:
                    b = p.chromium.launch(headless=True, args=GPU_ARGS, **kw)
                except Exception:
                    print(f"[info] browser: {name} not available"); continue
                gl = has_webgl2(b)
                print(f"[ok] browser: {name} {b.version}, WebGL2: {'yes' if gl else 'no'}")
                launched.append(name); webgl += [name] if gl else []
                b.close()
        report("headless browser", bool(launched), "python3 -m playwright install chromium   (or install Google Chrome)")
        if launched:
            print(f"[info] renderer will use: {webgl[0] if webgl else launched[0]}")
        if launched and not webgl:
            print("[warn] no browser has WebGL2: tell the user, and do not offer plans that need WebGL shaders, three.js or p5.brush")

    if has_ff:
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        if "chromakey" in filters:
            print("[ok] ffmpeg chromakey (green-screen compositing)")
        else:
            print("[warn] ffmpeg has no chromakey filter; green-screen plans need a fuller ffmpeg build")


def check_node(need):
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip() if shutil.which("node") else ""
    major = int(v.lstrip("v").split(".")[0]) if v else 0
    report(f"Node.js >= {need}{f' (found {v})' if v else ''}", major >= need, f"install Node.js {need}+ from https://nodejs.org")


def check_extra(name):
    if name in ("remotion", "hyperframes"):
        check_node(18 if name == "remotion" else 22)   # the HyperFrames CLI needs Node.js 22+
        if name == "remotion":
            print("[info] remotion: installed per project by `npx create-video@latest`, nothing global to check")
        else:
            print("[info] hyperframes: also install its skill: npx skills add heygen-com/hyperframes")
    elif name == "manim":
        report("manim", bool(shutil.which("manim")), "see https://docs.manim.community/en/stable/installation.html")
        if not shutil.which("latex"):
            print("[info] LaTeX not found: only needed for Tex / MathTex (macOS: brew install --cask mactex-no-gui)")
    elif name == "yt-dlp":
        report("yt-dlp (download reference videos)", bool(shutil.which("yt-dlp")), "python3 -m pip install yt-dlp   (or brew install yt-dlp)")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--only", nargs="+", choices=EXTRAS, help="check only these extras instead of the base tools")
a = ap.parse_args()
if a.only:
    for name in dict.fromkeys(a.only):
        check_extra(name)
else:
    check_base()
print("\nready" if ok else "\nsome tools are missing, see above")
sys.exit(0 if ok else 1)
