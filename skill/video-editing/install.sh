#!/usr/bin/env bash
# Installs the video-editing skill for Claude Code (Mac / Linux). No API keys involved.
set -e
SKILL_SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills/video-editing"
VENV="$HOME/.vedit-venv"

echo "1/4 Checking ffmpeg..."
if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then brew install ffmpeg
  else echo "ffmpeg is missing. Mac: install Homebrew (brew.sh) then run 'brew install ffmpeg'. Linux: 'sudo apt install ffmpeg'. Then rerun this script."; exit 1; fi
fi

echo "2/4 Checking Python 3..."
command -v python3 >/dev/null || { echo "Python 3 is missing. Install it from python.org, then rerun."; exit 1; }

echo "3/4 Creating private Python environment and installing faster-whisper..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip faster-whisper "av<17" pillow numpy

echo "4/4 Installing the skill into Claude Code..."
mkdir -p "$DEST"
cp -R "$SKILL_SRC/SKILL.md" "$SKILL_SRC/scripts" "$SKILL_SRC/styles" "$DEST/"

"$VENV/bin/python" "$DEST/scripts/vedit.py" check
echo "Done. Open Claude Code and say: 'Edit ~/Downloads/myvideo.mp4 into a captioned reel.'"
