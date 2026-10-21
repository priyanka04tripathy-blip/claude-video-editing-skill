# Setup (about 10 minutes)

You only do this once. After each step there is a line telling you how to know it worked. If it didn't, stop and go to [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Step 1. Open a terminal

- **Mac:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** press the Windows key, type `PowerShell`, press Enter.

You will paste commands here. Paste one, press Enter, wait for it to finish.

## Step 2. Install Claude Code

Follow the current official instructions: https://code.claude.com/docs/en/overview

You need a paid Claude plan (Pro or above) to sign in.

**Worked if:** typing `claude --version` prints a version number.

## Step 3. Get this project

```bash
git clone https://github.com/priyanka04tripathy-blip/claude-video-editing-skill
```

No git? Click the green **Code** button on GitHub, choose **Download ZIP**, and unzip it.

**Worked if:** a folder called `claude-video-editing-skill` now exists.

## Step 4. Run the installer

**Mac / Linux**
```bash
cd claude-video-editing-skill/skill/video-editing
bash install.sh
```

**Windows (PowerShell)**
```powershell
cd claude-video-editing-skill\skill\video-editing
powershell -ExecutionPolicy Bypass -File install.ps1
```

On Windows, if it installs ffmpeg and says to close the window, do that, open a fresh PowerShell and run Step 4 again.

It installs ffmpeg if missing, creates a private Python environment, installs the free Whisper library, and copies the skill into Claude Code.

**Worked if:** the last lines say `[ok] ffmpeg`, `[ok] faster-whisper` and `All set.`

## Step 5. Make your first edit

1. Put a short test video (30 to 60 seconds, you talking) in your Downloads folder.
2. In the terminal, go to that folder and start Claude Code:
   ```bash
   cd ~/Downloads
   claude
   ```
3. Type:
   > Use the video-editing skill. Turn `myvideo.mp4` into a captioned reel.

The first run downloads the Whisper speech model (about 460 MB), so it is slower. Later runs are fast.

**Worked if:** a new file like `myvideo_edited.mp4` appears next to the original. Your original is never changed.

## Updating

Run `git pull` inside the project folder, then run the installer again.

## Uninstall

Delete the folders `~/.claude/skills/video-editing` and `~/.vedit-venv`.
