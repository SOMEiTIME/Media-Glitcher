# Media-Glitcher

Small Python 3 tool that glitches media files (images, video) by swapping and corrupting the raw file data, either by lines (the original mode) or by bytes. Personal/art project; tests are in `tests/`.

## Run
```
python3 media_glitcher.py input_file output_file [--swap I,F] [--corrupt I,F] [--byte-swap S,E] [--byte-corrupt E] [--bitflip R] [--repeat S,E] [--iframe-drop K] [--pframe-repeat E,C] [--pixel-sort K,L,H,A] [--preset NAME_OR_FILE] [--save-preset NAME_OR_FILE] [--header-length N] [--header-bytes N] [--target T] [--seed N]
python3 media_glitcher.py --list-presets
```
- Python 3 (ported from 2.7), stdlib only (it also runs in a-Shell on iPhone). The one exception is `--pixel-sort`, which imports NumPy lazily and uses ffmpeg for formats other than PPM; keep everything else working without them. Files are read as bytes; line mode decodes them as latin-1 so binary data round-trips byte for byte.
- Don't run it on files in `examples/`; the output path gets overwritten.

## Layout
- `media_glitcher.py` — argparse CLI; one flag per entry in `engine.OPERATIONS`, run in the order given. Saved "good settings" are presets, not code.
- `engine.py` — `glitch(data, operations, ...)` runs operations with one seeded `random.Random`. A new operation needs an `OPERATIONS` entry, a function in `BYTE_FUNCTIONS` (or `LINE_FUNCTIONS`, `FRAME_FUNCTIONS` or `PIXEL_FUNCTIONS`), and help text in the CLI.
- `media.py` — line mode: `media` class splits the lines into header and body, exposes `glitch_random_swap(interval, flavour)` and `glitch_corrupt(interval, flavour)`, then `text()`.
- `byte_ops.py` — byte mode operations; each edits a bytearray in place and keeps the header and length.
- `avi.py` — frame mode: `split`/`join` an MPEG-4 AVI into video frames (keyframes found from the VOP header), `iframe_drop` and `pframe_repeat` (datamosh) as `engine.FRAME_FUNCTIONS`, and the `avi-frames` target. Frame operations change the file's length and drop its index, unlike byte operations.
- `jpeg.py` — JPEG marker parser for the `jpeg-scan`/`jpeg-tables` targets (`engine.FORMAT_TARGETS`). A target gives the byte ranges to glitch and a repair step afterwards (no stray FF in scan data, no zero quantization values).
- `uncompressed.py` — BMP, PPM/PGM/PBM, WAV and AIFF targets: find the raw data from the header, no repair needed. `engine.detect_target()` picks a target for `--target auto`. Don't use the stdlib `aifc` module (removed in Python 3.13, which a-Shell runs).
- `pixel_sort.py` — pixel mode: `pixel_sort(frame, key, low, high, angle)` on an H x W x 3 uint8 NumPy array (vectorized, no per-pixel loops), and `decode`, which reads PPM directly or another format through ffmpeg and returns the frame with a matching encoder. Uses no random draws, so seeded output of other operations doesn't change.
- `presets.py` — load/validate/save/apply presets; no CLI dependency, safe to import elsewhere.
- `presets/` — preset JSON files. `default` is what runs with no operations.
- `tests/` — `python3 -m unittest discover -s tests`. `tests/fixtures/` holds small JPEGs made with `cjpeg` (baseline, progressive, restart markers), a BMP made with Pillow and a WAV made with `wave`. Pixel-sort tests skip without NumPy, and their JPEG test skips without a working ffmpeg.
- `examples/` — sample outputs referenced by the README.

## Conventions and gotchas
- `header_length` (lines, line mode) and `header_bytes` (byte mode) are kept untouched so the file stays openable. Glitching the header just breaks the file.
- Line mode output must stay byte-identical (the golden tests check), so keep its line splitting and random draws as they are.
- Saved "good settings" are JSON files in `presets/` (format in `presets.py`) — keep them, and add new good ones rather than deleting. Use `--save-preset` to create one.
- Files are read in text mode line by line, so output is meant to be lossy and unpredictable. Not a bug.
- `.gitignore` ignores `__pycache__/`, `*.pyc` and `.DS_Store`.
- Style: comment blocks above each method, double-underscore private helpers.

## Public repo
This repo is public. Don't commit personal details (full name, email, local paths, device names), other people's contact info, or secrets. Ask first if a task needs one.

## Git workflow
- Never commit directly to `master`. Before making any commit, create a branch named for the work (e.g. `feature/add-glitch-mode`, `fix/header-parsing`, `docs/update-notes`) and commit there.
- If you're on `master` when asked to commit, switch to a new branch first.
- Keep commits small and focused, with a short imperative message.
- Pushing to a branch Claude created is fine without asking. Ask before force-pushing or pushing to any other branch (including `master`).
- Open a PR without asking once the work on a branch Claude created is done (tests pass, docs updated). For any other branch, ask first. Don't merge PRs.
- Before opening a PR, do a final pass over the whole diff against `master`: is it readable, well designed, and no more verbose than it needs to be? Fix what you find, without changing behaviour, then re-run the tests (`python3 -m unittest discover -s tests`) and note what the pass changed in the PR description.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
