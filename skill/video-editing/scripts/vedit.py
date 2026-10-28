#!/usr/bin/env python3
"""vedit - small, key-free video editing toolkit built on ffmpeg + faster-whisper.

Everything runs locally. No accounts, no API keys, no uploads.

Subcommands:
  check          verify ffmpeg / python / faster-whisper are ready
  transcribe     video -> word-level timestamps (.words.json) + .srt
  cut-silence    remove dead air and long pauses
  captions       burn styled captions (from .words.json) into the video
  overlay        burn a text overlay (hook, title, CTA) for a time range
  export         resize/crop to a platform preset (reel, linkedin-*, ...)
  reel           one-shot: cut silence -> transcribe -> captions -> export
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PRESETS = {
    "reel": (1080, 1920),               # Instagram Reels / TikTok / Shorts (9:16)
    "linkedin-portrait": (1080, 1350),  # LinkedIn feed, 4:5
    "linkedin-square": (1080, 1080),    # LinkedIn / Instagram feed, 1:1
    "linkedin-landscape": (1920, 1080),  # LinkedIn / YouTube, 16:9
}

# ASS colours are &HBBGGRR& (blue-green-red), so these are written that way.
COLORS = {
    "white": "FFFFFF", "yellow": "00E5FF", "black": "000000",
    "red": "3B3BFF", "green": "5EE05E", "orange": "2E8BFF", "pink": "B469FF",
}


def ass_color(c):
    """Colour name from COLORS, or a #RRGGBB hex code (brand colours)."""
    if c in COLORS:
        return COLORS[c]
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", c)
    if not m:
        die(f"Unknown colour '{c}'. Use a name ({', '.join(COLORS)}) or a hex code like #FFF1A8.")
    h = m.group(1).upper()
    return h[4:6] + h[2:4] + h[0:2]


def color_arg(c):
    ass_color(c)
    return c


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True):
    p = subprocess.run(cmd, capture_output=quiet, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "")[-1500:]
        die(f"command failed: {' '.join(cmd[:3])} ...\n{tail}")
    return p


def need_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found. Install ffmpeg first (see SETUP.md).")


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height:format=duration",
               "-of", "json", path]).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return int(s["width"]), int(s["height"]), float(d["format"]["duration"])


def has_audio(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
               "-show_entries", "stream=codec_type", "-of", "csv=p=0", path]).stdout
    return "audio" in out


def encode_args():
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart"]


# --------------------------------------------------------------------- check
def cmd_check(_):
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        print(f"[{'ok' if found else 'MISSING'}] {tool}")
        ok &= bool(found)
    print(f"[ok] python {sys.version.split()[0]}")
    try:
        import faster_whisper  # noqa: F401
        print("[ok] faster-whisper")
    except ImportError:
        print("[MISSING] faster-whisper  ->  pip install faster-whisper")
        ok = False
    print("\nAll set." if ok else "\nFix the MISSING items above, then run check again.")
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------- transcribe
def fmt_srt(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def transcribe(video, model="small", language=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("faster-whisper is not installed. Run: pip install faster-whisper")
    print(f"Transcribing with Whisper '{model}' (first run downloads the model)...")
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = m.transcribe(video, word_timestamps=True, language=language,
                                  vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": round(w.start, 3),
                          "end": round(w.end, 3)})
    base = os.path.splitext(video)[0]
    with open(base + ".words.json", "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=1)
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i in range(0, len(words), 7):
            chunk = words[i:i + 7]
            f.write(f"{i // 7 + 1}\n{fmt_srt(chunk[0]['start'])} --> "
                    f"{fmt_srt(chunk[-1]['end'])}\n"
                    f"{' '.join(w['word'] for w in chunk)}\n\n")
    print(f"Detected language: {info.language}. {len(words)} words.")
    print(f"Wrote {base}.words.json and {base}.srt")
    return base + ".words.json"


def cmd_transcribe(a):
    need_ffmpeg()
    transcribe(a.input, a.model, a.language)


# --------------------------------------------------------------- cut-silence
def detect_silence(path, noise_db, min_silence):
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
         f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"],
        capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def keep_segments(silences, duration, pad):
    keep, cursor = [], 0.0
    for s, e in silences:
        s = max(s, 0.0)
        seg_end = min(s + pad, duration)
        if seg_end - cursor > 0.05:
            keep.append((cursor, seg_end))
        if e is None or e >= duration - 0.05:  # silence runs to the end of the file
            cursor = duration
            break
        cursor = max(e - pad, 0.0)
    if duration - cursor > 0.05:
        keep.append((cursor, duration))
    return keep


def cut_silence(inp, out, noise_db=-30, min_silence=0.5, pad=0.12):
    need_ffmpeg()
    _, _, dur = probe(inp)
    audio = has_audio(inp)
    if not audio:
        die("This video has no audio track, so there is no silence to detect.")
    keep = keep_segments(detect_silence(inp, noise_db, min_silence), dur, pad)
    if not keep:
        die("Nothing left after cutting. Try a lower threshold, e.g. --threshold -40.")
    kept = sum(e - s for s, e in keep)
    print(f"Keeping {kept:.1f}s of {dur:.1f}s ({dur - kept:.1f}s removed, "
          f"{len(keep)} segments).")
    parts, labels = [], []
    for i, (s, e) in enumerate(keep):
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    graph = "".join(parts) + "".join(labels) + f"concat=n={len(keep)}:v=1:a=1[v][a]"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(graph)
        script = f.name
    try:
        run(["ffmpeg", "-y", "-hide_banner", "-i", inp,
             "-filter_complex_script", script, "-map", "[v]", "-map", "[a]",
             *encode_args(), out])
    finally:
        os.unlink(script)
    print(f"Wrote {out}")


def cmd_cut_silence(a):
    cut_silence(a.input, a.output, a.threshold, a.min_silence, a.pad)


# -------------------------------------------------------------- ASS builders
def ass_time(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def ass_header(w, h, font, size, primary, outline, bold, alignment, margin_v):
    return (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\n"
        f"PlayResX: {w}\nPlayResY: {h}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
        "MarginV, Encoding\n"
        f"Style: Default,{font},{size},&H00{primary}&,&H00{primary}&,&H00{outline}&,"
        f"&H80000000&,{-1 if bold else 0},0,0,0,100,100,0,0,1,{max(2, size // 14)},0,"
        f"{alignment},{int(w * 0.08)},{int(w * 0.08)},{margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n")


def esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_caption_ass(words, w, h, style, per_line, font, size, color, hilite):
    size = size or int(w * 0.075)
    margin_v = int(h * 0.22)  # keep captions clear of the platform UI at the bottom
    out = [ass_header(w, h, font, size, ass_color(color), COLORS["black"], True, 2, margin_v)]
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        label = [esc(c["word"]).upper() if style != "clean" else esc(c["word"])
                 for c in chunk]
        if style == "highlight":
            for j, c in enumerate(chunk):
                end = chunk[j + 1]["start"] if j + 1 < len(chunk) else c["end"]
                parts = [f"{{\\c&H00{ass_color(hilite)}&}}{label[k]}{{\\c&H00{ass_color(color)}&}}"
                         if k == j else label[k] for k in range(len(chunk))]
                out.append(f"Dialogue: 0,{ass_time(c['start'])},{ass_time(end)},Default,,"
                           f"0,0,0,,{' '.join(parts)}\n")
        else:
            out.append(f"Dialogue: 0,{ass_time(chunk[0]['start'])},"
                       f"{ass_time(chunk[-1]['end'])},Default,,0,0,0,,{' '.join(label)}\n")
    return "".join(out)


def burn_ass(inp, out, ass_text):
    """Burn an ASS file. Runs ffmpeg inside the temp dir so the filter path is a bare
    filename (avoids Windows drive-letter / space escaping problems)."""
    inp, out = os.path.abspath(inp), os.path.abspath(out)
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "t.ass"), "w", encoding="utf-8") as f:
            f.write(ass_text)
        p = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-i", inp, "-vf", "ass=t.ass",
                            *encode_args(), out], cwd=d, capture_output=True, text=True)
        if p.returncode != 0:
            die(f"burning text failed:\n{p.stderr[-1500:]}")
    print(f"Wrote {out}")


def cmd_captions(a):
    need_ffmpeg()
    words_path = a.words or os.path.splitext(a.input)[0] + ".words.json"
    if not os.path.exists(words_path):
        words_path = transcribe(a.input, a.model, a.language)
    with open(words_path, encoding="utf-8") as f:
        words = json.load(f)
    if not words:
        die("No speech found, so there is nothing to caption.")
    w, h, _ = probe(a.input)
    burn_ass(a.input, a.output, build_caption_ass(
        words, w, h, a.style, a.words_per_line, a.font, a.size, a.color, a.highlight))


def cmd_overlay(a):
    need_ffmpeg()
    w, h, dur = probe(a.input)
    end = a.end if a.end is not None else dur
    align = {"top": 8, "center": 5, "bottom": 2}[a.position]
    margin_v = int(h * {"top": 0.12, "center": 0, "bottom": 0.22}[a.position])
    size = a.size or int(w * 0.07)
    ass = ass_header(w, h, a.font, size, ass_color(a.color), COLORS["black"], True,
                     align, margin_v)
    ass += (f"Dialogue: 0,{ass_time(a.start)},{ass_time(end)},Default,,0,0,0,,"
            f"{esc(a.text)}\n")
    burn_ass(a.input, a.output, ass)


# -------------------------------------------------------------------- export
def export(inp, out, preset, fit="crop"):
    need_ffmpeg()
    tw, th = PRESETS[preset]
    if fit == "crop":
        vf = (f"scale={tw}:{th}:force_original_aspect_ratio=increase,"
              f"crop={tw}:{th},setsar=1")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-i", inp, "-vf", vf]
    else:  # blur: whole frame kept, blurred copy fills the rest
        graph = (f"[0:v]split[a][b];"
                 f"[a]scale={tw}:{th}:force_original_aspect_ratio=increase,"
                 f"crop={tw}:{th},boxblur=30:5[bg];"
                 f"[b]scale={tw}:{th}:force_original_aspect_ratio=decrease[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
        cmd = ["ffmpeg", "-y", "-hide_banner", "-i", inp,
               "-filter_complex", graph, "-map", "[v]", "-map", "0:a?"]
    run(cmd + encode_args() + [out])
    print(f"Wrote {out} ({tw}x{th})")


def cmd_export(a):
    export(a.input, a.output, a.preset, a.fit)


# ---------------------------------------------------------------------- reel
def cmd_reel(a):
    need_ffmpeg()
    with tempfile.TemporaryDirectory() as d:
        cut = os.path.join(d, "cut.mp4")
        if a.no_cut:
            shutil.copy(a.input, cut)
        else:
            cut_silence(a.input, cut, a.threshold, a.min_silence, a.pad)
        words_path = a.words or transcribe(cut, a.model, a.language)
        with open(words_path, encoding="utf-8") as f:
            words = json.load(f)
        if a.save_transcript:
            shutil.copy(words_path, os.path.splitext(a.output)[0] + ".words.json")
        w, h, _ = probe(cut)
        # export first so captions are sized for the final frame, then burn once
        sized = os.path.join(d, "sized.mp4")
        export(cut, sized, a.preset, a.fit)
        tw, th = PRESETS[a.preset]
        burn_ass(sized, a.output, build_caption_ass(
            words, tw, th, a.style, a.words_per_line, a.font, None, a.color, a.highlight))


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="vedit", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_cap_opts(p):
        p.add_argument("--style", choices=["highlight", "bold", "clean"],
                       default="highlight")
        p.add_argument("--words-per-line", type=int, default=3)
        p.add_argument("--font", default="Arial")
        p.add_argument("--color", type=color_arg, default="white")
        p.add_argument("--highlight", type=color_arg, default="yellow")

    def add_asr_opts(p):
        p.add_argument("--model", default="small",
                       help="tiny/base/small/medium. small is the best speed/accuracy default")
        p.add_argument("--language", default=None, help="e.g. en, hi. Default: auto-detect")

    def add_silence_opts(p):
        p.add_argument("--threshold", type=float, default=-30,
                       help="dB below which audio counts as silence (default -30)")
        p.add_argument("--min-silence", type=float, default=0.5,
                       help="shortest pause to remove, in seconds (default 0.5)")
        p.add_argument("--pad", type=float, default=0.12,
                       help="breathing room kept around speech (default 0.12s)")

    sub.add_parser("check").set_defaults(fn=cmd_check)

    p = sub.add_parser("transcribe")
    p.add_argument("input"); add_asr_opts(p); p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("cut-silence")
    p.add_argument("input"); p.add_argument("output"); add_silence_opts(p)
    p.set_defaults(fn=cmd_cut_silence)

    p = sub.add_parser("captions")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--words", help="existing .words.json (skips transcription)")
    p.add_argument("--size", type=int, default=None)
    add_asr_opts(p); add_cap_opts(p); p.set_defaults(fn=cmd_captions)

    p = sub.add_parser("overlay")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--text", required=True)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--position", choices=["top", "center", "bottom"], default="top")
    p.add_argument("--size", type=int, default=None)
    p.add_argument("--font", default="Arial")
    p.add_argument("--color", type=color_arg, default="white")
    p.set_defaults(fn=cmd_overlay)

    p = sub.add_parser("export")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--preset", choices=PRESETS, default="reel")
    p.add_argument("--fit", choices=["crop", "blur"], default="crop",
                   help="crop = fill frame; blur = keep whole frame on blurred background")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("reel")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--preset", choices=PRESETS, default="reel")
    p.add_argument("--fit", choices=["crop", "blur"], default="crop")
    p.add_argument("--words", help="existing .words.json (skips transcription)")
    p.add_argument("--no-cut", action="store_true", help="skip silence removal")
    p.add_argument("--save-transcript", action="store_true")
    add_silence_opts(p); add_asr_opts(p); add_cap_opts(p); p.set_defaults(fn=cmd_reel)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
