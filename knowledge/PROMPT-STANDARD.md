# Seedance prompt standard — 369 production (locked 23 Sep 2026, rule set v7.7)

Derived from the `seedance-film-director` skill, validated on the santan drama (v1 → v2 rebuild).
Numbers here are for OUR lane (Crun Seedance 2.0 FAST, 10s, 16:9, 480p, r2v, max 9 refs), not the skill's 2.5 numbers.
Load the skill before authoring shots; this card is the house implementation of it.

## The five rules that actually changed our output

1. **Never describe a face when a plate is attached.** No features, no skin tone. Text describing a face competes
   with the reference and loses — the model builds a generic person instead of reading the plate. Write only:
   *"the exact person shown in @ImageN, face and hair unchanged, wearing exactly the outfit from that plate.
   Do not alter their features."*
2. **Never use the word "cinematic."** In training data it attaches to game trailers and VFX — that is why v1
   looked rendered. Use *location documentary capture* + coarse grain, two colour temperatures, haze between lens
   and subject, soft corners, vignetting, clipped highlights, heavy shadows, closing with *nothing is perfectly
   sharp, perfectly exposed or perfectly composed.*
3. **Every reference gets one job AND a do-not-copy clause.** Our character plates are white-background
   split-screens, so each must carry: *"Do not copy the white studio background, the split-screen layout, the
   passport framing or the standing pose from @ImageN."* Without it the plate's background leaks in.
4. **Name every body in frame.** An unattributed shoulder, hand or background figure makes the model invent a
   person who is not in the cast — the santan clip-7 bug. Ship a CAST block.
5. **Always write an ENDING STATE.** Most important checklist item for us: the last frame of each clip is the
   continuity reference for the next one.

## Block order (positive throughout, negatives only in the closing list)

FORMAT · LOOK · REFERENCE ROLES · CAST · SETTING · STARTING STATE · TIMELINE · CAMERA · CONTINUITY · AUDIO ·
ENDING STATE · CONSTRAINTS

- **TIMELINE** — 10s = 3 beats (0–3.5 / 3.5–7 / 7–10); ~3–4 beats per 15s. Fewer and it stalls, more and it
  rushes. Each block starts from the state the last one left. **Cause before reaction.**
- **CAMERA** — a place in the frame, an event that triggers each move, an axis rule. Lock screen sides:
  *"X holds screen-left and Y screen-right for the entire runtime; they never swap sides and the camera never
  crosses between them."*
- **AUDIO** — positive first or the model suppresses the line. Language on **every** line. Then exclude
  background voices, other people speaking, voices from another room, television, radio, music.
- **Emotion as behaviour.** Not "she's furious" → *"her hands stop moving; she does not blink."* Protect the
  pauses: give silence its own timestamped beat and say nothing happens in it.

## Coverage

Two people in frame both talking is the hardest thing to generate (ByteDance names multi-subject interaction as a
known weakness). Shot/reverse-shot = one identity, one mouth per generation. Inserts need no face and no lip-sync.
For physical contact, reblock into two single-subject shots rather than fighting it.

## Chaining across clips

Extract the final frame, pass it as a reference to the next clip with its own narrow job (*"controls only the
room, its light and where people are standing; do not copy its framing"*). Chain within a location, **reset at
every location/time cut**. Never retell the previous clip — each prompt is standalone.

## Pre-flight check

- [ ] Under 5,000 characters
- [ ] No face/skin/feature described anywhere a plate is attached
- [ ] Every ref: one job + do-not-copy clause; ref numbers match upload order
- [ ] CAST block present; every frame-edge body attributed
- [ ] Every spoken line carries its language; speaker named; others silent
- [ ] Background voices / TV / radio / music excluded
- [ ] Beats timestamped, state carried forward, cause before reaction
- [ ] Screen sides locked
- [ ] ENDING STATE written
- [ ] Negatives only in closing CONSTRAINTS
- [ ] Prompt standalone

## Builder
`tools/santan_build2.py` — scene registry (`chars / loc / chain_from / sides / start / beats[3] / camera /
lines / ending`) → assembled blocks. Copy for the next production.
