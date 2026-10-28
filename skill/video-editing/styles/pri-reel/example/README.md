# Example spec

`spec.json` is the exact edit behind Pri's "3 ChatGPT shortcuts" reel. Copy it next to your footage and change:

| Field | Meaning |
|---|---|
| `talk`, `screen`, `words` | Raw talking video, screen recording, and the `.words.json` from `vedit.py transcribe` (times are source seconds) |
| `rotate` | `none`, `cw` or `ccw` if the phone file is stored sideways |
| `face_x` | Where the face is horizontally after rotation, 0-1 (0.5 = center) |
| `segments` | `[start, end]` source ranges to KEEP, in order. Everything else is cut |
| `commands` | The typed command line: `type` / `erase`, at a source time (`at`) or relative to the outro (`at_outro`) |
| `popups` | Cut-ins. Each has a window (`start`, `end`) and `phases`: a `clip` (chat view from the screen recording, `screen_ss` + `dur`) then a `still` (result image, `screen_ss` + `crop_y` rows of the screen recording to keep) |
| `punches` | Source times of key words that get a zoom punch |
| `captions` | `merge` multi-word fixes (`"chat gpd": "ChatGPT"`), `replace`, `max_words` |
| `outro` | CTA card text. Remove the block for no outro |
| `music` | `"generate"`, a path to your own MP3, or `null` for none |

Run:  `python reel_engine.py spec.json out.mp4`   (add `--limit 8` for a quick preview)
