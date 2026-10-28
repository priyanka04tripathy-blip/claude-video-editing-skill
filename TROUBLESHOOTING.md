# Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg: command not found` | Mac: `brew install ffmpeg` (get Homebrew at brew.sh). Windows: `winget install Gyan.FFmpeg`, then open a **new** PowerShell. Linux: `sudo apt install ffmpeg`. |
| `python3: command not found` / `python is not recognized` | Install Python 3 from python.org. On Windows tick **Add Python to PATH**. |
| Installer says `externally-managed-environment` | You ran an old pip command by hand. Use the installer: it makes its own private environment. |
| `[MISSING] faster-whisper` | Rerun the installer. It must finish without errors. |
| Claude says the skill wasn't found | Check the folder `~/.claude/skills/video-editing` exists and contains `SKILL.md`. Restart Claude Code. |
| First edit seems stuck | It is downloading the Whisper model (about 460 MB). Wait. It only happens once. |
| Model download fails | Your network blocks Hugging Face. Try another network or a phone hotspot for the first run. |
| Captions have wrong words | Ask for `--model medium`, or say the language ("this video is in Hindi"). You can also correct the `.words.json` file and rerun captions. |
| Cuts chop off the start of sentences | Increase padding: "keep 0.2 seconds around speech". |
| Silences are not being removed | Background noise or music is counted as sound. Ask for a threshold of -25. |
| Captions appear in a weird font | The font name isn't on your computer. Ask for a font you have, e.g. Arial or Helvetica. |
| Hindi / non-Latin captions show as boxes | Pick a font that includes those characters (e.g. Noto Sans, Mangal) via the font option. |

Still stuck? Open an [Issue](../../issues) and paste the exact error text. Never paste anything that looks like a key or password.

## Reel-engine problems

| Problem | Fix |
|---|---|
| My face is sideways or upside down | Phone files are sometimes stored sideways. Set `"rotate"` in the spec to `cw` or `ccw` (Claude checks a still frame first) |
| `ModuleNotFoundError: PIL` or `numpy` | Rerun the installer. It installs Pillow and numpy into the private environment |
| `faster-whisper` crashes with `metadata_errors` | A too-new `av` library. The installer pins `av<17`; rerun it |
| A sharp "ts" or "pop" in my voice | The skill compresses harsh highs automatically. If one survives, tell Claude the timestamp and it will treat that spot |
| A notification banner shows in a screen cut-in | Tell Claude the second it appears. Cut-ins are chosen from clean seconds, and it can pick another |
| Captions don't match what I said | Edit `talk.words.json` (fix the `word`, keep the times), or add a fix in the spec's `captions.merge` / `captions.replace` |
