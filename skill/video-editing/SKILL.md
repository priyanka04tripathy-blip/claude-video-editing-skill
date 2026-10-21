---
name: video-editing
description: Edit videos from plain-English requests, locally and free. Cuts silence and dead air, adds word-highlight captions, adds hook/title text overlays, and exports for Instagram Reels, LinkedIn, and YouTube sizes. Use when the user asks to edit, trim, caption, subtitle, resize, or "make a reel" from a video file.
---

# Video Editing

Local, key-free editing with `ffmpeg` + `faster-whisper`. Nothing is uploaded and no API keys are needed. Never ask the user for an API key for this skill.

## Run the tool

Use the Python from the skill's virtual environment, never the system Python:

- Mac/Linux: `~/.vedit-venv/bin/python ~/.claude/skills/video-editing/scripts/vedit.py <command>`
- Windows: `%USERPROFILE%\.vedit-venv\Scripts\python.exe %USERPROFILE%\.claude\skills\video-editing\scripts\vedit.py <command>`

If that path does not exist, tell the user to run the installer from the repo's SETUP.md and stop.

Run `check` first in a new session. If anything shows MISSING, fix that before editing.

## Commands

| Command | What it does |
|---|---|
| `check` | Verifies ffmpeg and faster-whisper |
| `transcribe IN` | Writes `IN.words.json` and `IN.srt` |
| `cut-silence IN OUT` | Removes pauses. `--threshold -30` (lower = only cut quieter), `--min-silence 0.5`, `--pad 0.12` |
| `captions IN OUT` | Burns captions. `--style highlight\|bold\|clean`, `--words-per-line 3`, `--color`, `--highlight`, `--font` |
| `overlay IN OUT --text "..."` | Text for a time range. `--start`, `--end`, `--position top\|center\|bottom` |
| `export IN OUT` | `--preset reel\|linkedin-portrait\|linkedin-square\|linkedin-landscape`, `--fit crop\|blur` |
| `reel IN OUT` | Whole pipeline: cut silence, transcribe, export, caption |

## How to work

1. Confirm the input file path and the destination platform. Default to `reel` (1080x1920) for Instagram, `linkedin-portrait` (1080x1350) for LinkedIn feed.
2. **Never overwrite the original.** Always write to a new file such as `name_edited.mp4`.
3. For a standard talking-head clip, run `reel` in one go. For anything custom, chain the individual commands. Silence must be cut **before** transcribing, so caption timing matches the edited video.
4. After the first pass, tell the user what changed in numbers (seconds removed, output size, output path) and ask what to adjust. Don't claim a result looks good, because you cannot watch the video. Offer to extract a still frame to check caption placement.
5. Tuning guide:
   - Cuts feel too aggressive: raise `--min-silence` to 0.8 and `--pad` to 0.2.
   - Background noise stops silence being detected: raise `--threshold` to -25.
   - Captions wrong: edit `.words.json` (fix the `word` fields, keep the timestamps), then rerun `captions --words`.
   - Whisper `small` is the default. Use `--model medium` for accents or non-English speech (slower).
   - Landscape source going to a reel: use `--fit blur` to keep the whole frame instead of cropping the sides.
6. First transcription downloads the Whisper model (about 460 MB for `small`). Warn the user once.

## Limits to be honest about

- It cannot see the video. It cuts on audio and draws text by position, so it does not know where a face is. Crop is centered.
- No music, B-roll insertion, or color grading. Say so rather than improvising a hack.
