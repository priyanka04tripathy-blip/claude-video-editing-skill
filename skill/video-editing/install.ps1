# Installs the video-editing skill for Claude Code (Windows PowerShell). No API keys involved.
$ErrorActionPreference = "Stop"
$src  = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:USERPROFILE ".claude\skills\video-editing"
$venv = Join-Path $env:USERPROFILE ".vedit-venv"

Write-Host "1/4 Checking ffmpeg..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  Write-Host "ffmpeg installed. CLOSE this window, open a new PowerShell, and run this script again."
  exit 0
}

Write-Host "2/4 Checking Python 3..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is missing. Install it from python.org (tick 'Add to PATH'), then rerun."; exit 1
}

Write-Host "3/4 Creating private Python environment and installing faster-whisper..."
python -m venv $venv
& "$venv\Scripts\pip.exe" install --quiet --upgrade pip faster-whisper

Write-Host "4/4 Installing the skill into Claude Code..."
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item "$src\SKILL.md" $dest -Force
Copy-Item "$src\scripts" $dest -Recurse -Force

& "$venv\Scripts\python.exe" "$dest\scripts\vedit.py" check
Write-Host "Done. Open Claude Code and say: 'Edit C:\Users\me\Videos\myvideo.mp4 into a captioned reel.'"
