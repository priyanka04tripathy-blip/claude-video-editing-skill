# Storyboard format

Present **three** options before any editing. Pri picks one (or mixes: "A's hook, C's ending"). Keep each option scannable.

## How to present

1. One line on the source: length, what was said, what the screen recording contains, and what will be cut and why (stumbles, repeats).
2. Three options, each a table. Estimated times are output seconds after cuts and speed-up.
3. A recommendation (one sentence, with the reason).
4. The choices still needed: title text, command-line text per beat, CTA/keyword, music (generated or her MP3), speed.

### Option template

**Option A: <name>** (~NN s, 1.25x)  Hook: "<exact first line>"

| # | Time | She says | On screen | Command line | Cut-in | Sound |
|---|---|---|---|---|---|---|
| 1 | 0.0-2.0 | "..." | Speaker, punch-in on "<word>" | `/cmd` types | none | tick, title pop |
| 2 | 2.0-5.3 | "..." | Chat view then result reveal | `/cmd` | billboard result | whoosh, pop |
| ... | | | | | | |
| N | 27.2-29.6 | "okay, bye" | Outro card | `/200...` | none | bell |

Cuts made: <list of what is removed>.  Cost of this option: <e.g. drops the 3rd shortcut demo>.

## Typical option set for "demo" reels

- **A. Straight demo** (default): follows the spoken order; one cut-in per thing named; ends on the CTA.
- **B. Result-first hook**: opens with the best finished result for 1.5 s (no voice-over cut), then "here's how" and the demo.
- **C. Tight 20-second version**: only the two strongest demos, fastest speed (1.3x), same CTA.

Vary what actually differs (hook, order, length, which demos), not just the labels.

## After she chooses

1. Restate the final choice in 3 lines (so she can catch mistakes cheaply).
2. Write `spec.json` (see `example/spec.json`).
3. Render a preview of the first 8 s (`--limit 8`) only if the spec is new/unusual; otherwise render fully.
4. Deliver the file, the measured length and loudness, and the list of open items.
