---
name: video-editing
description: Edit videos from plain-English requests, locally and free. Cuts silence, captions, text overlays, platform exports, AND builds full "talking head + screen cut-in" reels (speed-up, typed command line, pop-up screen demos, music, clean voice) in a saved personal style. Always proposes storyboards first and edits only after the user picks one. Use when the user asks to edit, trim, caption, resize, or "make a reel" from video files.
---

# Video Editing

Local, key-free editing with `ffmpeg` + `faster-whisper` (+ numpy/Pillow for the reel engine). Nothing is uploaded and no API keys are needed. Never ask the user for an API key for this skill.

## Run the tools

Use the Python from the skill's virtual environment, never the system Python:

- Mac/Linux: `~/.vedit-venv/bin/python ~/.claude/skills/video-editing/scripts/<tool>.py ...`
- Windows: `%USERPROFILE%\.vedit-venv\Scripts\python.exe %USERPROFILE%\.claude\skills\video-editing\scripts\<tool>.py ...`

If that path does not exist, tell the user to run the installer from the repo's SETUP.md and stop. Run `vedit.py check` first in a new session.

## Two modes

**Quick edits** (one thing: cut silence, add captions, resize): use `vedit.py` directly, see the table below. No storyboard needed.

**Reels with a designed look** (speed-up, cut-ins, music, a saved style): follow the storyboard workflow below. This is the default for anything the user calls a "reel", a "video for Instagram/LinkedIn", or "edit this in my style".

## Storyboard-first workflow (do not skip)

The user wants to choose the structure before any editing happens. **Do not render until they have picked a storyboard.**

1. **Intake.** Get the raw talking video, any screen recordings, and the platform. Extract one still and **look at it to check orientation** (phone files are often stored sideways with no flag). Note audio level.
2. **Transcribe** with word timestamps: `vedit.py transcribe talk.mp4` writes `talk.words.json`. Read the transcript. Never place cut-ins from guesses.
3. **Scan the screen recording** (contact sheet at 1 fps) for clean moments and for things to avoid: notification banners, the pulled-down shade, keyboards, other apps, private messages.
4. **Propose three storyboards** using `styles/<style>/STORYBOARD_TEMPLATE.md`: beat tables with time, what is said, what is on screen, command line, cut-in, sound. State what gets cut and why, the final length (must respect the user's cap, e.g. 35 s), a recommendation, and the decisions still open (title text, command-line text, CTA keyword, music, speed). Then **stop and wait**.
5. **After the user picks** (they may mix options), restate the final choice in three lines, then write `spec.json` (format: `styles/pri-reel/example/`).
6. **Render:** `reel_engine.py spec.json out.mp4` (add `--limit 8` to preview the first 8 s of a new or unusual spec).
7. **QA before delivering**, never skip:
   - Extract frames at each cut-in, the typed-command moments, a caption and the outro, and look at them.
   - Measure loudness and peak (`ffmpeg -i out.mp4 -af ebur128=peak=true -f null -`): target about -14 LUFS, peak below -1.5 dB.
   - Check for harsh bursts (windows that are mostly above 4 kHz while loud).
   - Report the final length.
8. **Deliver** the file with: length, what was cut, what is estimated (e.g. brand hex codes), and what you could not verify (you cannot listen: ask the user to). Then iterate on their feedback by editing the spec, not by starting over.

## Styles (the user's saved look)

Styles live in `styles/<name>/` with a `STYLE.md` (the rules), a `STORYBOARD_TEMPLATE.md`, and an `example/spec.json`.

- `pri-reel`: Pri's style (@buildwithpri). Black frame, butter-yellow title, typed command line, speaker in a wide window, pastel-blue/butter-yellow palette, screen cut-ins over a blurred background, lowercase 2-3 word captions, 1.25x speed, under 35 s, music + soft SFX, "Comment 200"-style outro. **Use it by default when the user is Pri or says "my style".**
- A new user can say "create my style from this reference reel" (upload a screen recording of it). Study the frames, copy `pri-reel` to `styles/<their-name>/`, and rewrite `STYLE.md` and the engine colours/title/fonts in the spec to match. Do not copy another creator's reel one-to-one: take structure and pacing, not their branding or footage.
- When the user corrects something about their look ("captions lower", "no zoom punches"), save it in that style's `STYLE.md` so it holds for future videos.

## `vedit.py` commands (quick edits)

| Command | What it does |
|---|---|
| `check` | Verifies ffmpeg and faster-whisper |
| `transcribe IN` | Writes `IN.words.json` and `IN.srt` |
| `cut-silence IN OUT` | Removes pauses. `--threshold -30`, `--min-silence 0.5`, `--pad 0.12` |
| `captions IN OUT` | Burns captions. `--style highlight\|bold\|clean`, `--words-per-line 3`, `--color`, `--highlight` (names or `#hex`), `--font` |
| `overlay IN OUT --text "..."` | Text for a time range. `--start`, `--end`, `--position top\|center\|bottom` |
| `export IN OUT` | `--preset reel\|linkedin-portrait\|linkedin-square\|linkedin-landscape`, `--fit crop\|blur` |
| `reel IN OUT` | Simple one-shot: cut silence, transcribe, export, caption |

Rules for quick edits: confirm the input and platform; never overwrite the original (write `name_edited.mp4`); cut silence **before** transcribing; report numbers (seconds removed, output path); tune with `--min-silence 0.8 --pad 0.2` if cuts feel choppy, `--threshold -25` if noise stops silence detecting, `--model medium` for accents. The first transcription downloads the Whisper model (about 460 MB for `small`): warn the user once.

## Limits to be honest about

- It cannot see or hear the result. It edits by audio and text positions; it does not track faces (the reel engine centers on `face_x`).
- No licensed music: it generates an original track or uses an MP3 the user supplies. Warn that trending Instagram sounds can mute or flag business accounts.
- Brand colours must come from the user. Estimates must be labelled as estimates.
