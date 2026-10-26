#!/usr/bin/env python3
"""Frame-by-frame renderer for pages that expose window.render(t).

The page must define `window.render = (t) => {...}` that draws the frame at t seconds.
Optionally it can set `window.ready = false` while loading assets and flip it to true.

Examples
  still:   render.py page.html shot.png --still 2.5 --size 1920x1080
  stills:  render.py page.html qa/shot.png --still 1,6,10    (one browser session; writes qa/shot-t1.png, qa/shot-t6.png, ...)
  video:   render.py page.html out.mp4 --size 1920x1080 --fps 30 --duration 12 --audio mix.wav
  blur:    render.py page.html out.mp4 --size 1440x1440 --fps 60 --duration 14 --subframes 4
  segment: render.py page.html seg.mp4 --size 1920x1080 --fps 30 --start 8 --duration 4
  workers: render.py page.html out.mp4 --size 1920x1080 --fps 30 --duration 180 --workers 4
           (splits the frames into 4 segments rendered by 4 browsers at once, then joins them losslessly)
  sfx:     render.py page.html audio/sfx-timeline.json --sfx-events --duration 180
           (writes the page's window.sfxEvents, [{t, sound, gain}] or a function returning it, as the
            timeline audio_tools.py sfx reads; duplicate t + sound pairs are written once)
Query strings are allowed: render.py "page.html?raw=1" out.mp4 ...
The page is served over a local HTTP server rooted at the current directory (or the page's own folder when
it lies outside), so it can fetch() project files such as audio/voice.json and import local ES modules,
which file:// pages cannot. An http(s):// URL is opened as is.
Audio shorter than the video is padded with silence; the video length always follows --duration.
"""
import argparse, functools, http.server, json, os, pathlib, subprocess, sys, tempfile, threading, time, urllib.parse

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

GPU_ARGS = ["--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
if sys.platform == "darwin":
    GPU_ARGS.append("--use-angle=metal")


BROWSERS = ({}, {"channel": "chrome"}, {"channel": "msedge"})   # Playwright's Chromium, then Chrome, then Edge


def has_webgl2(browser):
    pg = browser.new_page(); pg.set_content("<canvas id=c></canvas>")
    ok = pg.evaluate("!!document.getElementById('c').getContext('webgl2')")
    pg.close(); return ok


def launch(p):
    """Use the first browser with WebGL2, in BROWSERS order; without one, the first that starts."""
    fallback, errors = None, []
    for kw in BROWSERS:
        try:
            b = p.chromium.launch(headless=True, args=GPU_ARGS, **kw)
        except Exception as e:  # try the next browser
            errors.append(f"{kw or 'bundled chromium'}: {str(e).splitlines()[0]}"); continue
        if has_webgl2(b):
            if fallback: fallback.close()
            return b
        if fallback: b.close()
        else: fallback = b
    if fallback:
        print("warning: no browser has WebGL2; WebGL shader, three.js and p5.brush pages will not render", file=sys.stderr)
        return fallback
    sys.exit("No usable browser. Run `python3 -m playwright install chromium` or install Google Chrome.\n" + "\n".join(errors))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(arg):
    """Return (url, server) for the page; server is None for an http(s) URL."""
    if arg.startswith(("http://", "https://")):
        return arg, None
    path, _, query = arg.partition("?")
    page, root = pathlib.Path(path).resolve(), pathlib.Path.cwd().resolve()
    if root not in page.parents:
        root = page.parent
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/{urllib.parse.quote(page.relative_to(root).as_posix())}"
    return url + (f"?{query}" if query else ""), server


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page"); ap.add_argument("out")
    ap.add_argument("--size", default="1920x1080", help="WIDTHxHEIGHT")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, help="seconds to render (video mode)")
    ap.add_argument("--start", type=float, default=0.0, help="first second to render")
    ap.add_argument("--still", help="render a PNG at this time, or at each of several comma-separated times")
    ap.add_argument("--subframes", type=int, default=1, help="samples per frame blended into motion blur")
    ap.add_argument("--audio", help="audio file to mux (trimmed to the video)")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--workers", type=int, default=1, help="browsers rendering segments in parallel (video mode)")
    ap.add_argument("--frames", choices=("jpeg", "png"), default="jpeg",
                    help="how video frames are captured: jpeg (quality 100, fast, default) or png (exact, slower)")
    ap.add_argument("--sfx-events", action="store_true", help="write window.sfxEvents to `out` as an SFX timeline JSON")
    a = ap.parse_args()
    W, H = map(int, a.size.lower().split("x"))
    if a.workers > 1 and a.still is None:
        return render_parallel(a)

    url, server = serve(a.page)
    with sync_playwright() as p:
        browser = launch(p)
        pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(url)
        pg.wait_for_function("typeof window.render === 'function' && (window.ready === undefined || window.ready === true)", timeout=60000)
        pg.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")

        if a.sfx_events:
            if not a.duration:
                sys.exit("--sfx-events needs --duration (the length of the SFX track)")
            ev = pg.evaluate("(e => typeof e === 'function' ? e() : e)(window.sfxEvents)")
            if not isinstance(ev, list):
                sys.exit("the page has no window.sfxEvents array (or function returning one)")
            seen, events = set(), []
            for e in sorted(ev, key=lambda e: e["t"]):
                key = (round(e["t"], 3), e["sound"])
                if key not in seen:
                    seen.add(key); events.append({**e, "t": key[0]})
            pathlib.Path(a.out).write_text(json.dumps({"duration": a.duration, "events": events}, indent=1))
            print(f"{a.out}: {len(events)} sound effects")
            browser.close()
            if server: server.shutdown()
            return

        if a.still is not None:
            try:
                times = [float(x) for x in a.still.split(",") if x.strip()]
            except ValueError:
                sys.exit(f"--still takes seconds, e.g. 2.5 or 1,6,10 (got {a.still})")
            out = pathlib.Path(a.out)
            for n, t in enumerate(times):
                # one time: write `out` as given; several: shot.png -> shot-t1.png, shot-t6.png, ...
                path = out if len(times) == 1 else out.with_name(f"{out.stem}-t{t:g}{out.suffix}")
                pg.evaluate("t => window.render(t)", t)
                path.write_bytes(pg.screenshot(type="png"))   # the first call also warms the page up
                if n == 0:
                    t0 = time.time()
                    for _ in range(3):               # time a few more to estimate the per-frame cost
                        pg.evaluate("t => window.render(t)", t); pg.screenshot(type="png")
                    per = (time.time() - t0) / 3
                print(f"{path}: still at t={t:g}s")
            print(f"{per:.2f}s per frame (render + screenshot)")
            browser.close()
            if server: server.shutdown()
            return

        if not a.duration:
            sys.exit("--duration is required for video output")
        sub = max(1, a.subframes)
        frames = round(a.fps * a.duration)
        blur = f"tmix=frames={sub}:weights={' '.join(['1'] * sub)},select='not(mod(n\\,{sub}))'," if sub > 1 else ""
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-c:v", "mjpeg" if a.frames == "jpeg" else "png",
               "-framerate", str(a.fps * sub), "-i", "-"]
        if a.audio:
            cmd += ["-ss", str(a.start), "-i", a.audio]
        cmd += ["-vf", f"{blur}setpts=N/({a.fps}*TB),format=yuv420p", "-r", str(a.fps), "-c:v", "libx264", "-crf", str(a.crf),
                "-g", str(a.fps), "-keyint_min", str(a.fps), "-sc_threshold", "0"]   # a keyframe every second: splice.py cuts there
        if a.audio:   # pad the audio with silence so -shortest always stops at the end of the video
            cmd += ["-af", "apad", "-c:a", "aac", "-b:a", "320k", "-shortest"]
        cmd.append(a.out)
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        # JPEG at quality 100 is visually lossless (about 53 dB against PNG) and several times faster to capture,
        # most of all on textured pages (grain, chalk, paper), where PNG encoding dominates the frame time
        shot = {"type": "jpeg", "quality": 100} if a.frames == "jpeg" else {"type": "png"}
        t0 = time.time()
        total = frames * sub
        def capture(t):
            # a busy GPU (several browsers at once, long WebGL renders) now and then stalls one screenshot past
            # Playwright's 30 s timeout: draw the frame again and retry before giving up
            for attempt in range(3):
                try:
                    pg.evaluate("t => window.render(t)", t)
                    return pg.screenshot(**shot)
                except PlaywrightTimeout:
                    if attempt == 2:
                        raise
                    print(f"  screenshot at t={t:.3f}s timed out; retrying", file=sys.stderr, flush=True)
        try:
            for i in range(total):
                ff.stdin.write(capture(a.start + i / (a.fps * sub)))
                if i and i % max(1, total // 10) == 0:
                    print(f"  {i}/{total} samples, {time.time() - t0:.0f}s", flush=True)
        except BaseException:
            ff.kill()   # do not leave ffmpeg waiting on a half-written file
            raise
        browser.close()
        if server: server.shutdown()
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    took = time.time() - t0
    print(f"{a.out}: {frames} frames x {sub} samples, {a.size} @ {a.fps}fps, rendered in {took:.1f}s ({took / total:.2f}s per sample)")


def render_parallel(a):
    """Render contiguous frame ranges in separate processes, join them with the concat demuxer, then add audio."""
    if not a.duration:
        sys.exit("--duration is required for video output")
    frames = round(a.fps * a.duration)
    n = max(1, min(a.workers, frames))
    # cut on whole seconds (multiples of fps) so the joined file keeps a keyframe every second
    cuts = sorted({min(frames, round(frames * k / n / a.fps) * a.fps) for k in range(n)} | {frames})
    if cuts[0] != 0: cuts.insert(0, 0)
    n = len(cuts) - 1
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="render-", dir=pathlib.Path(a.out).resolve().parent))
    segs, t0 = [tmp / f"seg{k:02d}.mp4" for k in range(n)], time.time()
    def start(k):
        cmd = [sys.executable, os.path.abspath(__file__), a.page, str(segs[k]), "--size", a.size, "--fps", str(a.fps),
               "--start", repr(a.start + cuts[k] / a.fps), "--duration", repr((cuts[k + 1] - cuts[k]) / a.fps),
               "--subframes", str(a.subframes), "--crf", str(a.crf), "--frames", a.frames]
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
    print(f"rendering {frames} frames in {n} parallel segments ...", flush=True)
    procs = {k: start(k) for k in range(n)}
    failed = [k for k, p in procs.items() if p.wait()]
    for _ in range(2):                         # render only the failed segments again, one at a time
        if not failed:
            break
        print(f"segments {failed} failed; rendering them again", file=sys.stderr, flush=True)
        failed = [k for k in failed if start(k).wait()]
    if failed:
        sys.exit(f"segments {failed} failed; partial output kept in {tmp}")
    (tmp / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt")]
    if a.audio:
        cmd += ["-ss", str(a.start), "-i", a.audio, "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:a", "aac", "-b:a", "320k", "-shortest"]
    if subprocess.run(cmd + ["-c:v", "copy", a.out]).returncode:
        sys.exit(f"joining the segments failed; they are in {tmp}")
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    took = time.time() - t0
    print(f"{a.out}: {frames} frames, {a.size} @ {a.fps}fps, {n} workers, rendered in {took:.1f}s ({took / frames:.2f}s per frame overall)")


if __name__ == "__main__":
    main()
