#!/usr/bin/env python3
"""Replace time ranges of a finished video with re-rendered segments, keeping the video's own audio.

  splice.py out/final.mp4 qa/seg-98.mp4@98 qa/seg-141.mp4@141
    replaces, for each SEGMENT@SECONDS, the frames from SECONDS for the segment's length with the segment's frames.

Make each segment with the same size and fps as the video, e.g. for a web page:
  render.py index.html qa/seg-98.mp4 --size 1920x1080 --fps 30 --start 98 --duration 4
Pass all segments of one round of fixes in a single call.

Lossless and fast: render.py puts a keyframe on every whole second, so when every segment starts on a whole
second and lasts whole seconds (or runs to the end), the pieces are joined without re-encoding, in seconds.
Otherwise the video track is re-encoded once for all segments; the audio is always copied unchanged.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
               "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_packets", "-of", "json", path])
    if out.returncode:
        sys.exit(f"cannot read {path}: {out.stderr.strip()}")
    s = json.loads(out.stdout)["streams"][0]
    num, den = map(int, s["r_frame_rate"].split("/"))
    return {"codec": s["codec_name"], "size": (s["width"], s["height"]), "pix": s["pix_fmt"],
            "fps": num / den, "frames": int(s["nb_read_packets"])}


def keyframes(path, fps):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries",
               "frame=pts_time", "-of", "csv=p=0", path]).stdout
    return {round(float(x) * fps) for x in out.replace(",", " ").split()}


def lossless(video, info, segs, tmp):
    """Join kept GOPs of `video` and the segments with stream copy; return False when that is not possible."""
    fps, n = info["fps"], info["frames"]
    keys = keyframes(video, fps)
    for path, first, last, si in segs:   # cut points must be keyframes of the original; a segment always starts on one
        if (si["codec"], si["pix"]) != (info["codec"], info["pix"]) or first not in keys or (last != n and last not in keys):
            return False
    parts, pos = [], 0
    for k, (path, first, last, _) in enumerate(segs + [(None, n, n, None)]):
        if first > pos:                      # untouched stretch of the original, whole GOPs
            piece = tmp / f"keep{k:02d}.mp4"
            if run(["ffmpeg", "-v", "error", "-y", "-ss", f"{pos / fps:.6f}", "-i", video, "-frames:v", str(first - pos),
                    "-map", "0:v", "-c", "copy", str(piece)]).returncode:
                return False
            parts.append(piece)
        if path:
            piece = tmp / f"seg{k:02d}.mp4"
            if run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map", "0:v", "-c", "copy", str(piece)]).returncode:
                return False
            parts.append(piece)
        pos = last
    (tmp / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
    out = tmp / "joined.mp4"
    if run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-i", video,
            "-map", "0:v", "-map", "1:a?", "-c", "copy", str(out)]).returncode:
        return False
    return probe(str(out))["frames"] == n and out


def reencode(video, info, segs, tmp, crf):
    fps, n = info["fps"], info["frames"]
    # untouched stretches of the original between the segments
    keep = [(a, b) for a, b in zip([0] + [s[2] for s in segs], [s[1] for s in segs] + [n]) if b > a]
    chains = [f"[0:v]split={len(keep)}" + "".join(f"[o{i}]" for i in range(len(keep)))] if keep else ["[0:v]nullsink"]
    parts, ki = [], 0
    for k, (path, first, last, _) in enumerate(segs):
        if ki < len(keep) and keep[ki][1] == first:
            a, b = keep[ki]
            chains.append(f"[o{ki}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[k{ki}]"); parts.append(f"[k{ki}]"); ki += 1
        chains.append(f"[{k + 1}:v]setpts=PTS-STARTPTS[s{k}]"); parts.append(f"[s{k}]")
    if ki < len(keep):                       # the stretch after the last segment
        a, b = keep[ki]
        chains.append(f"[o{ki}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[k{ki}]"); parts.append(f"[k{ki}]")
    chains.append(f"{''.join(parts)}concat=n={len(parts)}:v=1:a=0,format=yuv420p[v]")
    out = tmp / "joined.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", video] + sum((["-i", s[0]] for s in segs), []) + [
        "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "0:a?", "-r", f"{fps:g}", "-c:v", "libx264",
        "-crf", str(crf), "-g", str(round(fps)), "-keyint_min", str(round(fps)), "-sc_threshold", "0", "-c:a", "copy", str(out)]
    r = run(cmd)
    if r.returncode:
        sys.exit(f"ffmpeg failed: {r.stderr.strip()[:300]}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("segments", nargs="+", metavar="SEGMENT@SECONDS")
    ap.add_argument("--crf", type=int, default=16, help="quality when the video track has to be re-encoded")
    a = ap.parse_args()

    info = probe(a.video)
    fps, n = info["fps"], info["frames"]
    segs = []
    for spec in a.segments:
        path, sep, at = spec.rpartition("@")
        if not sep or not path:
            sys.exit(f"write each segment as PATH@SECONDS, e.g. qa/seg.mp4@98 (got {spec})")
        si = probe(path)
        if si["size"] != info["size"] or abs(si["fps"] - fps) > 1e-3:
            sys.exit(f"{path} is {si['size'][0]}x{si['size'][1]} @ {si['fps']:g}fps but the video is "
                     f"{info['size'][0]}x{info['size'][1]} @ {fps:g}fps; re-render the segment to match")
        first = round(float(at) * fps)
        segs.append((path, first, first + si["frames"], si))
    segs.sort(key=lambda s: s[1])
    for (p1, f1, l1, _), (p2, f2, l2, _) in zip(segs, segs[1:]):
        if f2 < l1:
            sys.exit(f"{p1} and {p2} overlap; merge them into one segment")
    if segs[0][1] < 0 or segs[-1][2] > n:
        sys.exit(f"a segment falls outside the video's {n} frames; check the @ seconds and segment lengths")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="splice-", dir=pathlib.Path(a.video).resolve().parent))
    try:
        out = lossless(a.video, info, segs, tmp)
        how = "joined without re-encoding"
        if not out:
            out = reencode(a.video, info, segs, tmp, a.crf)
            how = "video track re-encoded once (start segments on whole seconds and make them whole seconds long to skip this)"
        os.replace(out, a.video)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for path, first, last, _ in segs:
        print(f"{a.video}: {first / fps:g}s-{last / fps:g}s replaced from {path}")
    print(how)


if __name__ == "__main__":
    main()
