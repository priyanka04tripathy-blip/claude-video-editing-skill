#!/usr/bin/env python3
"""reel_engine - render a "talking head + screen cut-in" reel from a JSON edit spec.

    python reel_engine.py spec.json out.mp4 [--limit 8] [--workdir DIR]

Layout (the "pri-reel" style): black 1080x1920 frame, title on top, a typed command line,
the speaker in a wide window, screen-recording cut-ins over a blurred background, simple
captions below, outro card. Audio: cleaned voice + generated (or supplied) music ducked under
the voice + typing/whoosh/pop sound effects.

Everything is local. Needs ffmpeg, numpy, Pillow. Edit decisions (what to cut, when each
cut-in appears) live in the spec so they can be reviewed and changed without touching code.
See ../styles/pri-reel/ for the spec format and ../SKILL.md for the workflow.
"""
import argparse, json, math, os, re, subprocess, sys, tempfile, time, wave
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FPS, SR, CW, CH = 30, 48000, 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))


def die(msg): sys.exit(f"ERROR: {msg}")


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode: die(f"{' '.join(cmd[:3])} failed:\n{p.stderr[-2500:]}")
    return p


def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def find_font(names):
    dirs = ["/usr/share/fonts", "/Library/Fonts", "/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
            os.path.expanduser("~/Library/Fonts"), "C:/Windows/Fonts", HERE + "/../assets"]
    for n in names:
        for d in dirs:
            for r, _, fs in os.walk(d):
                if n in fs: return os.path.join(r, n)
    return None


def load_font(kind, size):
    pref = {"black": ["Inter-Black.otf", "Arial Black.ttf", "ariblk.ttf", "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
            "bold": ["Inter-Bold.otf", "Arial Bold.ttf", "arialbd.ttf", "Helvetica.ttc", "DejaVuSans-Bold.ttf"],
            "mono": ["DejaVuSansMono-Bold.ttf", "Courier New Bold.ttf", "courbd.ttf", "Menlo.ttc", "Monaco.ttf"]}[kind]
    p = find_font(pref)
    try: return ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
    except Exception: return ImageFont.load_default(size)


class Reel:
    def __init__(self, spec, work, limit=0):
        self.s, self.work, self.limit = spec, work, limit
        c = spec.get("colors", {})
        self.BUTTER = hexrgb(c.get("butter", "#FFF1A8")); self.BLUE = hexrgb(c.get("blue", "#BFD9F2"))
        self.NAVY = hexrgb(c.get("navy", "#1F3A5F"))
        self.speed = spec.get("speed", 1.25); self.outro_len = spec.get("outro", {}).get("length", 2.4) if spec.get("outro") else 0
        self.segs = [tuple(x) for x in spec["segments"]]
        self.offs, acc = [], 0.0
        for a, b in self.segs: self.offs.append(acc); acc += b - a
        self.main = acc / self.speed; self.total = self.main + self.outro_len
        self.seg_out = [(o / self.speed, (o + b - a) / self.speed) for (a, b), o in zip(self.segs, self.offs)]
        self.win_y, self.win_h = 565, 886
        self.talk = spec["talk"]; self.screen = spec.get("screen")
        w = probe_size(self.talk)
        self.rot = spec.get("rotate", "none")
        self.src_w, self.src_h = (w[1], w[0]) if self.rot in ("cw", "ccw") else w
        self.face_x = spec.get("face_x", 0.5) * self.src_w
        self.rot_vf = {"cw": "transpose=1,", "ccw": "transpose=2,", "none": ""}[self.rot]
        self.fonts = dict(title=load_font("black", 68), cmd=load_font("mono", 66), cap=load_font("bold", 70))
        print(f"main {self.main:.1f}s + outro {self.outro_len}s = {self.total:.1f}s")
        self._schedule(); self._popups(); self._captions()

    # ------------------------------------------------ timeline helpers
    def W(self, t):                                   # source seconds -> output seconds
        for (a, b), o in zip(self.segs, self.offs):
            if a <= t <= b: return (o + t - a) / self.speed
        for (a, b), o in zip(self.segs, self.offs):
            if t < a: return o / self.speed
        return self.main

    def _t(self, d, key="at"):                        # a time from a spec item
        if "at_outro" in d: return self.main + d["at_outro"]
        if "at_out" in d: return d["at_out"]
        return self.W(d[key])

    def _schedule(self):
        self.keys, cur = [], ""
        for ev in self.s.get("commands", []):
            t0 = self._t(ev)
            if ev["op"] == "type":
                for i, ch in enumerate(ev["text"]): cur += ch; self.keys.append((t0 + i * 0.055, cur))
            else:
                for i in range(len(cur)): self.keys.append((t0 + i * 0.028, cur[:-1 - i]))
                cur = ""
        self.punch = [self.W(t) for t in self.s.get("punches", [])]

    def cmd_at(self, t):
        s = ""
        for kt, ks in self.keys:
            if kt <= t: s = ks
            else: break
        return s

    # ------------------------------------------------ screen-recording cut-ins
    def _read(self, ss, dur, vf):
        p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(ss), "-t", str(dur), "-i", self.screen, "-vf",
                            f"fps={FPS},{vf}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        return p.stdout

    def _popups(self):
        self.pops = []
        if not self.screen: return
        sw, sh_ = probe_size(self.screen); cy0, cy1 = self.s.get("chat_crop", [int(sh_ * .078), int(sh_ * .80)])
        for p in self.s.get("popups", []):
            phases = []
            for ph in p["phases"]:
                t0 = self._t(ph)
                if ph["kind"] == "clip":
                    h = cy1 - cy0; raw = self._read(ph["screen_ss"], ph.get("dur", 3), f"crop={sw}:{h}:0:{cy0}")
                    n = len(raw) // (sw * h * 3)
                    img = [Image.frombytes("RGB", (sw, h), raw[i * sw * h * 3:(i + 1) * sw * h * 3]) for i in range(n)]
                    phases.append((t0, "clip", img, (515, 886)))
                else:
                    y0, y1 = ph["crop_y"]; raw = self._read(ph["screen_ss"], 0.1, f"crop={sw}:{y1 - y0}:0:{y0}")
                    phases.append((t0, "still", Image.frombytes("RGB", (sw, y1 - y0), raw[:sw * (y1 - y0) * 3]), (960, 840)))
            self.pops.append(dict(a=self._t(p, "start"), b=self._t(p, "end"), ph=phases))
        print("cut-ins:", [(round(p["a"], 2), round(p["b"], 2)) for p in self.pops])

    # ------------------------------------------------ captions
    def _captions(self):
        cfg = self.s.get("captions", {})
        words = json.load(open(self.s["words"])) if self.s.get("words") else []
        kept = []
        for w in words:
            for (a, b), o in zip(self.segs, self.offs):
                if w["start"] >= a - .02 and w["end"] <= b + .05:
                    kept.append(dict(word=w["word"].strip(" .,!?"), start=(o + w["start"] - a) / self.speed,
                                     end=(o + w["end"] - a) / self.speed)); break
        merges = {tuple(k.lower().split()): v for k, v in cfg.get("merge", {}).items()}
        repl = {k.lower(): v for k, v in cfg.get("replace", {}).items()}
        out, i = [], 0
        low = [k["word"].lower() for k in kept]
        while i < len(kept):
            hit = None
            for key, val in sorted(merges.items(), key=lambda kv: -len(kv[0])):
                if tuple(low[i:i + len(key)]) == key: hit = (len(key), val); break
            if hit:
                out.append(dict(word=hit[1], start=kept[i]["start"], end=kept[i + hit[0] - 1]["end"])); i += hit[0]; continue
            if cfg.get("slash_commands", True) and low[i] == "slash" and i + 1 < len(kept):
                out.append(dict(word="/" + low[i + 1], start=kept[i]["start"], end=kept[i + 1]["end"])); i += 2; continue
            out.append(dict(word=repl.get(low[i], kept[i]["word"].lower() if cfg.get("lowercase", True) else kept[i]["word"]),
                            start=kept[i]["start"], end=kept[i]["end"])); i += 1
        mx = cfg.get("max_words", 3); chunks, c = [], []
        for w in out:
            if c and (len(c) >= mx or len(" ".join(x["word"] for x in c + [w])) > 22): chunks.append(c); c = []
            c.append(w)
        if c: chunks.append(c)
        self.chunks = chunks

    # ------------------------------------------------ drawing
    @staticmethod
    def ease(p):
        p = min(max(p, 0), 1); c1 = 1.70158; c3 = c1 + 1
        return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

    def title_layer(self):
        lines = self.s.get("title", ["Title"]); img = Image.new("RGBA", (1080, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        for i, ln in enumerate(lines[:2]): d.text((540, 62 + i * 78), ln, font=self.fonts["title"], fill=self.BUTTER, anchor="mm")
        return img

    def zoom_at(self, t):
        i = next((k for k, (a, b) in enumerate(self.seg_out) if a <= t < b), len(self.seg_out) - 1)
        a, b = self.seg_out[i]; p = (t - a) / max(b - a, 1e-6)
        z = 1.0 + 0.07 * (p if i % 2 == 0 else 1 - p)
        for pt in self.punch:
            if t >= pt: z += 0.075 * math.exp(-(t - pt) / 0.22) * min(1, (t - pt) / 0.05)
        return z

    def talk_window(self, img, z):
        s = self.win_h / self.src_h * z; cw, ch = CW / s, self.win_h / s
        cx = min(max(self.face_x, cw / 2), self.src_w - cw / 2); cy = self.src_h / 2
        return img.resize((CW, self.win_h), Image.LANCZOS, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))

    def blurred(self, win):
        sm = win.resize((54, 44), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
        return ImageEnhance.Brightness(sm.resize((CW, self.win_h), Image.BICUBIC)).enhance(0.55)

    def popup(self, t, bg):
        for p in self.pops:
            if not (p["a"] <= t < p["b"]): continue
            k = max(i for i, x in enumerate(p["ph"]) if x[0] <= t); t0, kind, payload, (fw, fh) = p["ph"][k]
            im = payload[min(int((t - t0) * FPS), len(payload) - 1)] if kind == "clip" else payload
            sc = min(fw / im.width, fh / im.height)
            if kind == "still": sc *= 1 + 0.035 * min(1.5, t - t0)
            enter = self.ease((t - t0) / 0.25) if (k == 0 or kind == "still") else 1
            scale = (0.88 + 0.12 * enter) if k == 0 else (0.94 + 0.06 * enter)
            w2, h2 = max(2, int(im.width * sc * scale)), max(2, int(im.height * sc * scale))
            content = im.resize((w2, h2), Image.LANCZOS)
            alpha = min(1, (t - p["a"]) / 0.12) if k == 0 else 1.0
            if t > p["b"] - 0.12: alpha = min(alpha, (p["b"] - t) / 0.12)
            mask = Image.new("L", (w2, h2), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w2 - 1, h2 - 1), 30, fill=int(255 * alpha))
            shadow = Image.new("L", (w2 + 60, h2 + 60), 0)
            ImageDraw.Draw(shadow).rounded_rectangle((30, 40, w2 + 30, h2 + 40), 34, fill=int(120 * alpha))
            out = bg.copy(); x, y = (CW - w2) // 2, (self.win_h - h2) // 2
            out.paste((0, 0, 0), (x - 30, y - 30), shadow.filter(ImageFilter.GaussianBlur(14)))
            out.paste(content, (x, y), mask); return out
        return None

    def caption(self, d, t):
        ch = None
        for c in self.chunks:
            if c[0]["start"] - 0.02 <= t < c[-1]["end"] + 0.18: ch = c
        if not ch: return
        f = self.fonts["cap"]; ws = [w["word"] for w in ch]; sp = f.getlength(" "); wd = [f.getlength(x) for x in ws]
        x = (CW - (sum(wd) + sp * (len(ws) - 1))) / 2; act = max([i for i, w in enumerate(ch) if w["start"] <= t] or [0])
        for i, w in enumerate(ws):
            d.text((x, 1630), w, font=f, fill=self.BUTTER if i == act else (255, 255, 255), anchor="ls"); x += wd[i] + sp

    def outro_window(self, t):
        o = self.s["outro"]; p = self.ease((t - self.main) / 0.35); sc = lambda v: int(v * (0.85 + 0.15 * p))
        win = Image.new("RGB", (CW, self.win_h)); d = ImageDraw.Draw(win)
        pw, ph_ = sc(900), sc(210); cy = 250
        d.rounded_rectangle(((CW - pw) // 2, cy - ph_ // 2, (CW + pw) // 2, cy + ph_ // 2), sc(60), fill=self.BLUE)
        d.text((540, cy), o.get("headline", ""), font=load_font("black", sc(108)), fill=self.NAVY, anchor="mm")
        d.text((540, 520), o.get("line1", ""), font=load_font("bold", sc(58)), fill=(255, 255, 255), anchor="mm")
        d.text((540, 600), o.get("line2", ""), font=load_font("bold", sc(58)), fill=(255, 255, 255), anchor="mm")
        d.text((540, 760), o.get("handle", ""), font=load_font("bold", sc(50)), fill=self.BLUE, anchor="mm")
        return win

    # ------------------------------------------------ audio
    def synth_audio(self):
        rng = np.random.default_rng(7); n = int((self.total + 1) * SR); T = self.total
        def put(buf, sig, at, g):
            i = int(at * SR); j = min(n, i + len(sig))
            if 0 <= i < n: buf[i:j] += sig[:j - i] * g
        def tone(f, dur, decay, harm=(1, .5, .25)):
            t = np.arange(int(dur * SR)) / SR; return sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harm)) * np.exp(-t * decay)
        note = lambda m: 440 * 2 ** ((m - 69) / 12)
        music = self.s.get("music", "generate")
        if music not in (None, "generate"):                     # user-supplied track
            sh(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", music, "-t", f"{T + 1}", "-ar", str(SR), "-ac", "2",
                "-af", f"afade=t=in:d=0.5,afade=t=out:st={T - 1.4:.2f}:d=1.4", f"{self.work}/music.wav"])
        elif music == "generate":
            beat = 60 / 118; mus = np.zeros(n)
            prog = [(48, [60, 64, 67, 71]), (43, [59, 62, 67, 74]), (45, [60, 64, 69, 72]), (41, [60, 65, 69, 72])]
            for b in range(int((T + 1) / (4 * beat)) + 2):
                root, ch = prog[b % 4]; t0 = b * 4 * beat
                pad = sum(tone(note(m - 12), 4 * beat + .3, .55, (1, .3)) for m in ch)
                put(mus, pad * np.minimum(1, np.arange(len(pad)) / (SR * .25)), t0, .055)
                for s_ in range(8): put(mus, tone(note(ch[[0, 1, 2, 3, 2, 1, 2, 3][s_]] + 12), .5, 7, (1, .45, .2)), t0 + s_ * beat / 2, .11)
                for bt in (0, 1.5, 2, 3.5): put(mus, tone(note(root), .45, 5, (1, .3)), t0 + bt * beat, .20)
                for bt in (0, 2):
                    tt = np.arange(int(.18 * SR)) / SR
                    put(mus, np.sin(2 * np.pi * (50 * tt + 90 * (1 - np.exp(-tt * 30)) / 30)) * np.exp(-tt * 22), t0 + bt * beat, .55)
                for bt in (1, 3):
                    tt = np.arange(int(.14 * SR)) / SR; put(mus, rng.standard_normal(len(tt)) * np.exp(-tt * 30), t0 + bt * beat, .045)
                for s_ in range(1, 8, 2):
                    tt = np.arange(int(.05 * SR)) / SR; put(mus, np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt * 90), t0 + s_ * beat / 2, .03)
            ir = rng.standard_normal(int(1.1 * SR)) * np.exp(-np.arange(int(1.1 * SR)) / SR * 4.5); L = n + len(ir)
            wet = np.fft.irfft(np.fft.rfft(mus, L) * np.fft.rfft(ir, L), L)[:n]
            mus = mus + 0.12 * wet / (np.abs(wet).max() + 1e-9) * np.abs(mus).max()
            d = int(beat * .75 * SR); mus[d:] += 0.28 * mus[:-d]
            mus = np.convolve(mus, np.ones(4) / 4, "same"); mus /= np.abs(mus).max(); mus *= 0.9
            fade = np.ones(n); fade[:int(.5 * SR)] = np.linspace(0, 1, int(.5 * SR)); ed = int(T * SR)
            fade[ed - int(1.4 * SR):ed] = np.linspace(1, 0, int(1.4 * SR)); fade[ed:] = 0
            self._wav(mus * fade, "music")
        # sound effects
        sfx = np.zeros(n); tt = np.arange(int(.012 * SR)) / SR
        tick = (np.convolve(rng.standard_normal(len(tt)), np.ones(4) / 4, "same") * .5 + np.sin(2 * np.pi * 1700 * tt)) * np.exp(-tt * 260)
        for kt, _ in self.keys: put(sfx, tick, kt, .17)
        def whoosh(dur=.42, f0=300, f1=5200):
            m = int(dur * SR); x = rng.standard_normal(m); out = np.zeros(m); frames = 24; hop = m // frames
            for k in range(frames):
                c = f0 * (f1 / f0) ** (k / frames); seg = x[k * hop:(k + 2) * hop]; S = np.fft.rfft(seg); ff = np.fft.rfftfreq(len(seg), 1 / SR)
                S *= np.exp(-0.5 * (np.log2((ff + 1) / c) / .55) ** 2); out[k * hop:k * hop + len(seg)] += np.fft.irfft(S, len(seg)) * np.hanning(len(seg))
            out *= np.sin(np.linspace(0, np.pi, m)) ** 1.5; return out / (np.abs(out).max() + 1e-9)
        def bloop(f0, f1, dur=.11):
            t = np.arange(int(dur * SR)) / SR; return np.sin(2 * np.pi * np.cumsum(f0 + (f1 - f0) * t / dur) / SR) * np.exp(-t * 28)
        wh, wh_s = whoosh(), whoosh(.28, 600, 7000)
        for p in self.pops:
            put(sfx, wh, p["a"] - .05, .5); put(sfx, wh_s, p["b"] - .1, .28)
            for ph in p["ph"][1:]: put(sfx, bloop(520, 900), ph[0], .38)
        put(sfx, bloop(420, 820, .14), .05, .35)
        if self.outro_len:
            t = np.arange(int(1.2 * SR)) / SR
            put(sfx, (np.sin(2 * np.pi * 1319 * t) + .5 * np.sin(2 * np.pi * 1976 * t) + .25 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 4.2), self.main + .05, .35)
        self._wav(sfx / (np.abs(sfx).max() + 1e-9) * .9, "sfx")

    def _wav(self, x, name):
        pcm = (np.stack([np.clip(x, -1, 1)] * 2, 1) * 32767).astype("<i2").tobytes()
        with wave.open(f"{self.work}/{name}.wav", "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)

    def build_voice(self):
        n = len(self.segs); parts = "".join(
            f"[t{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={b - a - .015:.3f}:d=0.015[a{i}];"
            for i, (a, b) in enumerate(self.segs))
        g = (f"[0:a]asplit={n}" + "".join(f"[t{i}]" for i in range(n)) + ";" + parts + "".join(f"[a{i}]" for i in range(n))
             + f"concat=n={n}:v=0:a=1[c];"
             "[c]highpass=f=85,adeclick,afftdn=nr=10:nf=-30,equalizer=f=220:t=q:w=1:g=-2.5,equalizer=f=3200:t=q:w=1.1:g=1.5,asplit=2[lo][hi];"
             "[lo]lowpass=f=4500[lo2];"      # split-band: tame harsh t/s/p bursts (above 4.5 kHz) without dulling the voice
             "[hi]highpass=f=4500,acompressor=threshold=-40dB:ratio=14:attack=0.5:release=45:makeup=1[hi2];"
             "[lo2][hi2]amix=inputs=2:normalize=0,treble=g=-2:f=7000,"
             "acompressor=threshold=-22dB:ratio=3:attack=8:release=120:makeup=4,"
             f"atempo={self.speed},loudnorm=I=-16:TP=-3:LRA=7,aformat=sample_rates={SR}:channel_layouts=stereo,apad=whole_dur={self.total + 1}[v]")
        open(f"{self.work}/v.txt", "w").write(g)
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", self.talk, "-filter_complex_script", f"{self.work}/v.txt", "-map", "[v]",
            "-t", f"{self.total + 1}", f"{self.work}/voice.wav"])

    def mix(self):
        ins = ["-i", f"{self.work}/voice.wav", "-i", f"{self.work}/sfx.wav"]
        mus = os.path.exists(f"{self.work}/music.wav") and self.s.get("music", "generate") is not None
        if mus: ins += ["-i", f"{self.work}/music.wav"]
        g = ("[0:a]asplit=2[vo][sc];[2:a]volume=0.5[mu];[mu][sc]sidechaincompress=threshold=0.02:ratio=9:attack=12:release=380:makeup=1[du];"
             "[vo][du][1:a]amix=inputs=3:weights=1 0.9 0.7:normalize=0," if mus else "[0:a][1:a]amix=inputs=2:weights=1 0.7:normalize=0,")
        sh(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex",
            g + f"alimiter=limit=0.8,loudnorm=I=-14:TP=-2:LRA=7,atrim=0:{self.total:.3f}[o]", "-map", "[o]", "-c:a", "aac", "-b:a", "192k",
            f"{self.work}/mix.m4a"])

    # ------------------------------------------------ video
    def render(self):
        N = int(round(self.total * FPS)); N = min(N, int(self.limit * FPS)) if self.limit else N
        k = len(self.segs)
        g = (f"[0:v]{self.rot_vf}split={k}" + "".join(f"[s{i}]" for i in range(k)) + ";"
             + "".join(f"[s{i}]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(self.segs))
             + "".join(f"[v{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0,setpts=PTS/{self.speed},fps={FPS},format=rgb24[v]")
        open(f"{self.work}/g.txt", "w").write(g)
        dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", self.talk, "-filter_complex_script", f"{self.work}/g.txt",
                                "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{CW}x{CH}", "-r", str(FPS),
                                "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", f"{self.work}/video.mp4"],
                               stdin=subprocess.PIPE)
        fsz = self.src_w * self.src_h * 3; last = None; title = self.title_layer(); t0 = time.time()
        for f in range(N):
            t = f / FPS; raw = dec.stdout.read(fsz)
            if len(raw) == fsz: last = Image.frombytes("RGB", (self.src_w, self.src_h), raw)
            base = Image.new("RGB", (CW, CH)); d = ImageDraw.Draw(base)
            sc = 0.8 + 0.2 * self.ease(t / 0.4); tl = title.resize((int(1080 * sc), int(200 * sc)), Image.LANCZOS)
            if t < 0.2: tl.putalpha(tl.getchannel("A").point(lambda v, a=t / 0.2: int(v * a)))
            base.paste(tl, ((CW - tl.width) // 2, 215 + (200 - tl.height) // 2), tl)
            ul = int(330 * min(1, max(0, (t - .15) / .45))); d.rectangle((540 - ul // 2, 425, 540 + ul // 2, 428), fill=self.BLUE)
            s = self.cmd_at(t); w_ = self.fonts["cmd"].getlength(s); x0 = (CW - w_) / 2
            d.text((x0, 502), s, font=self.fonts["cmd"], fill=self.BUTTER, anchor="ls")
            if int(t * 2) % 2 == 0 or any(abs(kt - t) < .25 for kt, _ in self.keys): d.rectangle((x0 + w_ + 6, 454, x0 + w_ + 12, 512), fill=self.BLUE)
            if t < self.main or not self.outro_len:
                win = self.talk_window(last, self.zoom_at(t)) if last else Image.new("RGB", (CW, self.win_h))
                pl = self.popup(t, self.blurred(win)); base.paste(pl if pl is not None else win, (0, self.win_y)); self.caption(d, t)
            else:
                base.paste(self.outro_window(t), (0, self.win_y))
            enc.stdin.write(base.tobytes())
            if f % 150 == 0: print(f"frame {f}/{N}  {time.time() - t0:.0f}s", flush=True)
        enc.stdin.close(); enc.wait(); dec.kill()


def probe_size(path):
    out = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path]).stdout.strip()
    w, h = out.split(",")[:2]; return int(w), int(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("output"); ap.add_argument("--limit", type=float, default=0, help="render only the first N seconds (preview)")
    ap.add_argument("--workdir", default=None)
    a = ap.parse_args()
    for t in ("ffmpeg", "ffprobe"):
        if not shutil_which(t): die(f"{t} not found")
    spec = json.load(open(a.spec)); base = os.path.dirname(os.path.abspath(a.spec))
    for k in ("talk", "screen", "words"):
        if spec.get(k) and not os.path.isabs(spec[k]): spec[k] = os.path.join(base, spec[k])
    if isinstance(spec.get("music"), str) and spec["music"] != "generate" and not os.path.isabs(spec["music"]): spec["music"] = os.path.join(base, spec["music"])
    work = a.workdir or tempfile.mkdtemp(prefix="reel_"); os.makedirs(work, exist_ok=True)
    r = Reel(spec, work, a.limit); r.synth_audio(); r.build_voice(); r.mix(); r.render()
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{work}/video.mp4", "-i", f"{work}/mix.m4a", "-c:v", "copy", "-c:a", "copy",
        "-shortest", "-movflags", "+faststart", a.output])
    print("Wrote", a.output)


def shutil_which(x):
    import shutil; return shutil.which(x)


if __name__ == "__main__":
    main()
