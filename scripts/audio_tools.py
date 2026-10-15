#!/usr/bin/env python3
"""Small audio toolkit: synthesize UI/motion sound effects on a timeline, mix the tracks, normalize loudness,
and draw waveform/spectrum images so the model can check audio it cannot hear.

  sfx:        audio_tools.py sfx audio/sfx-timeline.json audio/sfx.wav
  mix:        audio_tools.py mix audio/mix-raw.wav --music audio/music.wav --sfx audio/sfx.wav --voice audio/voice.wav
              (each track optional; music is lowered while the voice speaks)
  normalize:  audio_tools.py normalize audio/mix-raw.wav audio/mix.wav   (-14 LUFS, true peak below -1 dBTP)
  check:      audio_tools.py check audio/mix.wav --out qa/audio
  tts:        audio_tools.py tts audio/voice-script.txt audio/voice.wav --voice zh-CN-XiaoxiaoNeural --rate=-5%
              (edge-tts, sends the text to Microsoft's online service; also writes audio/voice.json with
               {"start", "end", "text", "para", "words": [{"start", "end", "text"}, ...]} for every sentence,
               the timeline the visuals follow;
               a blank line in the script ends a paragraph and inserts --pause seconds of silence, default 0.6;
               a paragraph that is only "[pause 5]" inserts 5 s of silence there instead)
  beats:      audio_tools.py beats music.mp3 > source/beats.json     (measure a supplied track)

beats.json: {"bpm": 120.0, "beats": [...], "downbeats": [...], "hits": [...]}
  beats = where state changes go, downbeats = where the big moments go, hits = where SFX go.
  Uses librosa when installed, otherwise a numpy-only tracker (fine for steady-tempo music).

timeline.json:
  {"duration": 12, "bpm": 120, "beat": "kick",            # optional soft pulse on every beat
   "events": [{"t": 1.0, "sound": "click"}, {"t": 2.0, "sound": "success", "gain": 0.8},
              {"t": 3.5, "sound": "whoosh"}, {"t": 4.0, "sound": "pop"}, {"t": 6.0, "sound": "impact"}]}
sounds: click, pop, success, whoosh, impact, tick, kick, riser
Music itself is better written per project (see references/craft-rules.md); this covers the effects layer.
"""
import argparse, json, re, subprocess, sys, wave

import numpy as np

SR = 48000


def env(n, attack=0.002, decay=0.1):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(attack, 1e-4)) * np.exp(-x / decay)


def tone(freqs, length, decay, attack=0.003):
    n = int(length * SR); x = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * x) for f in freqs) / len(freqs) * env(n, attack, decay)


def noise(length, seed=1):
    return np.random.default_rng(seed).standard_normal(int(length * SR))


def sweep(f0, f1, length):
    n = int(length * SR); f = np.geomspace(f0, f1, n)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(sig, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); out = np.zeros_like(sig); y = 0.0
    for i, s in enumerate(sig):
        y = (1 - a) * s + a * y; out[i] = y
    return out


SOUNDS = {
    "click": lambda: noise(0.04) * env(int(0.04 * SR), 0.0005, 0.005) * 0.6 + tone([2400], 0.04, 0.008) * 0.6,
    "tick": lambda: tone([3200], 0.03, 0.006),
    "pop": lambda: np.concatenate([tone([880], 0.06, 0.03), tone([1175, 1760], 0.4, 0.12)]),
    "success": lambda: np.concatenate([tone([1318.5], 0.09, 0.06), tone([1318.5, 1975.5], 0.5, 0.15)]),
    "whoosh": lambda: lowpass(noise(0.45, 7), 2500) * np.hanning(int(0.45 * SR)) * 2.2,
    "impact": lambda: sweep(160, 38, 0.6) * env(int(0.6 * SR), 0.001, 0.18) + lowpass(noise(0.6, 3), 900) * env(int(0.6 * SR), 0.001, 0.05),
    "kick": lambda: sweep(140, 45, 0.35) * env(int(0.35 * SR), 0.001, 0.12),
    "riser": lambda: sweep(200, 1800, 1.2) * np.linspace(0, 1, int(1.2 * SR)) ** 2 * 0.5 + lowpass(noise(1.2, 5), 4000) * np.linspace(0, 1, int(1.2 * SR)) ** 2 * 0.4,
}


def write_wav(path, sig):
    peak = np.abs(sig).max() or 1
    sig = sig / peak * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())


def place(out, s, t, gain):
    i = int(t * SR); n = min(len(s), len(out) - i)
    out[i:i + n] += s[:n] * gain


def cmd_sfx(a):
    spec = json.load(open(a.timeline)); dur = spec["duration"]
    names = ([spec["beat"]] if spec.get("beat") else []) + [ev["sound"] for ev in spec["events"]]
    unknown = sorted(set(names) - set(SOUNDS))
    if unknown:
        sys.exit(f"unknown sound {', '.join(unknown)}; choose from {', '.join(SOUNDS)}")
    outside = [ev["t"] for ev in spec["events"] if not 0 <= ev["t"] < dur]
    if outside:
        sys.exit(f"events outside 0-{dur}s at t = {outside}; fix the times or raise duration")
    out = np.zeros(int(dur * SR))
    if spec.get("beat"):
        for t in np.arange(0, dur, 60 / spec.get("bpm", 120)):
            place(out, SOUNDS[spec["beat"]](), t, 0.3)
    for ev in spec["events"]:
        place(out, SOUNDS[ev["sound"]](), ev["t"], ev.get("gain", 0.7))
    write_wav(a.out, out)
    print(f"{a.out}: {len(spec['events'])} events, {dur}s")


def cmd_mix(a):
    tracks = [(k, f) for k, f in (("music", a.music), ("sfx", a.sfx), ("voice", a.voice)) if f]
    if not tracks:
        sys.exit("give at least one of --music, --sfx, --voice")
    cmd, chains, labels = ["ffmpeg", "-v", "error", "-y"], [], []
    for i, (k, f) in enumerate(tracks):
        cmd += ["-i", f]
        chains.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo[{k}]")
    if a.music:
        chains.append(f"[music]volume={a.music_gain}dB[m0]")
        if a.voice:   # duck the music under the voice: the voice drives a compressor on the music
            chains += ["[voice]asplit=2[voice_mix][voice_key]", "[voice_key]apad[key]",   # pad so the music outlasts the voice
                       f"[m0][key]sidechaincompress=threshold=0.02:ratio={a.duck_ratio}:attack=20:release=400[m1]"]
            labels.append("[m1]")
        else:
            labels.append("[m0]")
    if a.sfx:
        labels.append("[sfx]")
    if a.voice:
        labels.append("[voice_mix]" if a.music else "[voice]")
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[out]")
    # 32-bit float keeps peaks above full scale intact for normalize; 16-bit would clip them here
    r = subprocess.run(cmd + ["-filter_complex", ";".join(chains), "-map", "[out]", "-c:a", "pcm_f32le", a.out])
    if r.returncode:
        sys.exit(r.returncode)
    print(f"{a.out}: mixed {', '.join(k for k, _ in tracks)}")


def group_sentences(text, words, para):
    """Split a paragraph at 。！？!? and line breaks; give each sentence the words found inside it, in order."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"[^。！？!?\n]+[。！？!?]*", text) if m.group().strip()]
    out, pos = [{"text": text[i:j].strip(), "para": para, "words": []} for i, j in spans], 0
    for w in words:
        at = text.find(w["text"], pos)
        if at < 0:      # the service normalized this word; leave it out rather than misplace it
            continue
        pos = at + len(w["text"])
        for s, (i, j) in zip(out, spans):
            if i <= at < j:
                s["words"].append(w); break
    for s in out:
        if s["words"]:
            s["start"], s["end"] = s["words"][0]["start"], s["words"][-1]["end"]
    missing = [s["text"] for s in out if not s["words"]]
    if missing:
        print(f"warning: no word timing for {missing}; they are left out of voice.json", file=sys.stderr)
    return [{"start": s["start"], "end": s["end"], "text": s["text"], "para": para, "words": s["words"]} for s in out if s["words"]]


def cmd_tts(a):
    try:
        import edge_tts
    except ImportError:
        sys.exit("edge-tts is not installed: python3 -m pip install edge-tts")
    import asyncio
    # paragraphs (blocks separated by blank lines) are synthesized one by one and joined with --pause seconds of
    # silence, so sections get a breath; sentences inside a paragraph keep their natural prosody
    # a paragraph that is only "[pause N]" is not spoken: it replaces the gap at that point with N seconds of silence
    paras = [p.strip() for p in re.split(r"\n\s*\n", open(a.script, encoding="utf-8").read()) if p.strip()]
    hold = lambda p: re.fullmatch(r"\[pause\s+([\d.]+)\]", p)
    pieces, sentences, t0, k = [], [], 0.0, 0

    async def stream(text, k):
        # edge-tts reports one boundary type per stream: take words and group them into sentences here
        mp3, words = bytearray(), []
        async for c in edge_tts.Communicate(text, a.voice, rate=a.rate, boundary="WordBoundary").stream():
            if c["type"] == "audio":
                mp3.extend(c["data"])
            elif c["type"] == "WordBoundary":       # offset and duration are in 100 ns units
                start = t0 + c["offset"] / 1e7
                words.append({"start": round(start, 3), "end": round(start + c["duration"] / 1e7, 3), "text": c["text"]})
        sentences.extend(group_sentences(text, words, k))
        return bytes(mp3)

    for i, text in enumerate(paras):
        if hold(text):
            pieces.append(np.zeros(int(float(hold(text)[1]) * SR)))
            t0 += len(pieces[-1]) / SR
            continue
        try:   # fail instead of hanging when the service refuses or stalls; about 1 s per 10 s of speech
            mp3 = asyncio.run(asyncio.wait_for(stream(text, k), timeout=max(60, len(text) / 2)))
        except Exception as e:
            sys.exit(f"edge-tts failed ({type(e).__name__}: {str(e)[:120]}). A 403 usually means the installed edge-tts is "
                     "too old for Microsoft's service: python3 -m pip install -U edge-tts. Otherwise check the network or proxy.")
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "mp3", "-i", "-", "-ar", str(SR), "-ac", "1", "-f", "f32le", "-"],
                           input=mp3, capture_output=True)
        if r.returncode:
            sys.exit(r.stderr.decode()[:300])
        sig = np.frombuffer(r.stdout, dtype=np.float32)
        last, before_hold = i == len(paras) - 1, i < len(paras) - 1 and hold(paras[i + 1])
        gap = np.zeros(0 if last or before_hold else int(a.pause * SR))
        pieces += [sig, gap]
        t0 += (len(sig) + len(gap)) / SR
        k += 1
    write_wav(a.out, np.concatenate(pieces))
    timeline = re.sub(r"\.[^.\/]+$", "", a.out) + ".json"
    json.dump(sentences, open(timeline, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    end = sentences[-1]["end"] if sentences else 0
    print(f"{a.out}: {k} paragraphs, {len(sentences)} sentences, speech ends at {end:.2f}s; timestamps in {timeline}")


def loudness(path):
    st = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = st[st.rfind("Summary:"):]
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary); peak = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return (float(lufs.group(1)) if lufs else None), (float(peak.group(1)) if peak else None)


def cmd_normalize(a):
    # gain to -14 LUFS plus a peak limiter, re-measured until within 0.5 LU: loudnorm alone falls short on peaky audio
    lufs, _ = loudness(a.inp)
    if lufs is None:
        sys.exit(f"could not measure loudness of {a.inp}")
    gain = -14 - lufs
    for _ in range(4):
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-af",
                            f"aresample={SR},volume={gain:.2f}dB,alimiter=limit=0.75:level=false:attack=1:release=50", a.out])
        if r.returncode:
            sys.exit(r.returncode)
        lufs, peak = loudness(a.out)
        if lufs is None:
            sys.exit(f"could not measure loudness of {a.out}; is the input silent?")
        if abs(lufs + 14) <= 0.5:
            break
        gain += -14 - lufs
    print(f"{a.out}: {lufs:.1f} LUFS, true peak {peak:.1f} dBFS")


def cmd_check(a):
    lufs, peak = loudness(a.inp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-filter_complex", "showwavespic=s=1600x300:split_channels=0", "-frames:v", "1", f"{a.out}-wave.png"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-lavfi", "showspectrumpic=s=1600x500:legend=1", f"{a.out}-spectrum.png"])
    print(f"integrated loudness: {lufs if lufs is not None else '?'} LUFS (target -14)   true peak: {peak if peak is not None else '?'} dBFS (keep below -1)")
    print(f"images: {a.out}-wave.png, {a.out}-spectrum.png  (look for clipping, silence gaps, low-frequency rumble)")


def load_mono(path, sr=22050):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def beats_numpy(y, sr):
    hop, n_fft = 256, 1024
    frames = 1 + (len(y) - n_fft) // hop
    win = np.hanning(n_fft)
    spec = np.abs(np.fft.rfft(np.stack([y[i * hop:i * hop + n_fft] * win for i in range(frames)]), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(axis=1)
    onset = np.concatenate([[0], flux]); onset = (onset - onset.mean()) / (onset.std() + 1e-9)
    fps = sr / hop
    # tempo: autocorrelation of the onset envelope, 60-180 BPM, mild preference around 120,
    # refined to a fractional period so the grid does not drift over long tracks
    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 60) + 1)
    score = ac[lags] * np.exp(-0.5 * (np.log2(60 * fps / lags / 120) / 0.9) ** 2)
    i = int(np.argmax(score)); period = float(lags[i])
    if 0 < i < len(score) - 1:
        l, c, r = score[i - 1], score[i], score[i + 1]
        period += 0.5 * (l - r) / (l - 2 * c + r) if (l - 2 * c + r) != 0 else 0
    n = len(onset)
    grid = lambda o: [int(round(o + k * period)) for k in range(int((n - o) / period) + 1) if round(o + k * period) < n]
    phase = max(range(int(period)), key=lambda o: onset[grid(o)].sum())
    # track: predict the next beat from the previous one, snap to a strong onset nearby
    beats, t, w = [], float(phase), max(2, int(period * 0.12))
    while t < n:
        c = int(round(t)); lo, hi = max(0, c - w), min(n, c + w + 1)
        j = lo + int(np.argmax(onset[lo:hi]))
        pos = j if onset[j] > 0.5 else c
        beats.append(pos); t = pos + period
    lag = n_fft / 2 / sr                       # frame index -> time at the window centre
    beat_t = np.array(beats) / fps + lag
    down0 = max(range(4), key=lambda k: onset[beats[k::4]].sum()) if len(beats) >= 4 else 0
    peaks = [i for i in range(1, n - 1) if onset[i] > 2 and onset[i] >= onset[i - 1] and onset[i] >= onset[i + 1]]
    hits, last = [], -10**9
    for i in peaks:
        if i - last > fps * 0.1: hits.append(i / fps + lag); last = i
    return 60 * fps / period, beat_t.tolist(), beat_t[down0::4].tolist(), hits


def cmd_beats(a):
    try:
        import librosa
        y, sr = librosa.load(a.inp, sr=None, mono=True)
        tempo, fr = librosa.beat.beat_track(y=y, sr=sr, units="frames")
        beats = librosa.frames_to_time(fr, sr=sr).tolist()
        env_ = librosa.onset.onset_strength(y=y, sr=sr)
        pk = librosa.util.peak_pick(env_, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
        # the downbeat is the beat phase (of 4) with the strongest onsets, as in beats_numpy
        down0 = max(range(min(4, len(fr))), key=lambda k: env_[fr[k::4]].sum()) if len(fr) else 0
        bpm, downs, hits = float(np.atleast_1d(tempo)[0]), beats[down0::4], librosa.frames_to_time(pk, sr=sr).tolist()
    except ImportError:
        y, sr = load_mono(a.inp)
        bpm, beats, downs, hits = beats_numpy(y, sr)
    r = lambda xs: [round(x, 3) for x in xs]
    json.dump({"bpm": round(bpm, 2), "beats": r(beats), "downbeats": r(downs), "hits": r(hits)}, sys.stdout, indent=1)
    print(f"\nbpm {bpm:.1f}, {len(beats)} beats, {len(hits)} hits", file=sys.stderr)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("sfx"); p.add_argument("timeline"); p.add_argument("out"); p.set_defaults(fn=cmd_sfx)
p = sp.add_parser("mix"); p.add_argument("out"); p.add_argument("--music"); p.add_argument("--sfx"); p.add_argument("--voice")
p.add_argument("--music-gain", type=float, default=-6, help="dB applied to the music before mixing")
p.add_argument("--duck-ratio", type=float, default=6, help="how hard the voice pushes the music down")
p.set_defaults(fn=cmd_mix)
p = sp.add_parser("tts"); p.add_argument("script"); p.add_argument("out")
p.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="edge-tts voice; list them with: edge-tts --list-voices")
p.add_argument("--rate", default="+0%", help="speaking rate, written with =, e.g. --rate=+10%% or --rate=-5%% (a bare -5%% is read as a flag)")
p.add_argument("--pause", type=float, default=0.6, help="seconds of silence at each blank line in the script")
p.set_defaults(fn=cmd_tts)
p = sp.add_parser("normalize"); p.add_argument("inp"); p.add_argument("out"); p.set_defaults(fn=cmd_normalize)
p = sp.add_parser("check"); p.add_argument("inp"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_check)
p = sp.add_parser("beats"); p.add_argument("inp"); p.set_defaults(fn=cmd_beats)
args = ap.parse_args(); args.fn(args)
