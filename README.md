# Claude Video Editing Skill

Tell Claude what you want in plain English. Get back an edited video.

> "Take `~/Downloads/raw.mp4`, cut the dead air, add yellow word-highlight captions, and export it as a reel."

**Free. Runs on your own computer. No API keys. Your videos are never uploaded anywhere.**

## What it does

| You say | It does |
|---|---|
| "Remove the silences" | Cuts pauses and dead air, keeps a natural breath between sentences |
| "Add captions" | Transcribes locally with Whisper, burns in styled captions (word-highlight, bold or clean) |
| "Add a hook at the top" | Puts text over the first few seconds |
| "Make it a reel / LinkedIn post" | Exports at the right size: 9:16, 4:5, 1:1 or 16:9 |
| "Do the whole thing" | Silence cut, captions and export in one pass |

## What you need

- A computer (Mac, Windows or Linux)
- [Claude Code](https://code.claude.com/docs/en/overview), which needs a paid Claude plan
- About 10 minutes and 1 GB of free disk space

## Install

Full walkthrough with a "this worked if..." check at every step: **[SETUP.md](SETUP.md)**.

Short version, after Claude Code is installed:

```bash
git clone https://github.com/priyanka04tripathy-blip/claude-video-editing-skill
cd claude-video-editing-skill/skill/video-editing
bash install.sh          # Windows: powershell -ExecutionPolicy Bypass -File install.ps1
```

Then open Claude Code and describe the edit. Copy-paste prompts are in **[PROMPTS.md](PROMPTS.md)**. If something breaks, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

## Privacy and keys

- No API keys are used anywhere in this project, so there is nothing of the author's to leak and nothing for you to paste in.
- Transcription runs on your machine. The only download is the free Whisper model, fetched once from Hugging Face.
- The installer only touches `~/.claude/skills/video-editing` and a private Python environment at `~/.vedit-venv`.
- Read the code before you run it. It is one file: [`vedit.py`](skill/video-editing/scripts/vedit.py).

## Limits

It edits by audio and text, not by looking at the picture. That means no face tracking (crops are centered), no B-roll insertion, no music and no color grading. Use `--fit blur` when a landscape clip would lose important parts to a center crop.

## License

MIT. Use it, change it, share it.

---
Built by [@buildwithpri](https://www.instagram.com/buildwithpri). If this saved you an hour of editing, share it with one person who edits their own reels.
