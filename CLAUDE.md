# Media-Glitcher

Small Python 3 tool that glitches media files (images, video) by swapping and corrupting the raw file data, either by lines (the original mode) or by bytes. Personal/art project; tests are in `tests/`.

## Run
```
python3 media_glitcher.py input_file output_file [--swap I,F] [--corrupt I,F] [--byte-swap S,E] [--byte-corrupt E] [--bitflip R] [--repeat S,E] [--preset NAME_OR_FILE] [--save-preset NAME_OR_FILE] [--header-length N] [--header-bytes N] [--seed N]
python3 media_glitcher.py --list-presets
```
- Python 3 (ported from 2.7), stdlib only (it also runs in a-Shell on iPhone). Files are read as bytes; line mode decodes them as latin-1 so binary data round-trips byte for byte.
- Don't run it on files in `examples/`; the output path gets overwritten.

## Layout
- `media_glitcher.py` — argparse CLI. One flag per operation type (generated from `engine.OPERATIONS`) plus `--preset`; operations run in the order given. Saved "good settings" are presets, not code.
- `engine.py` — `glitch(data, operations, header_length, header_bytes, seed)`: runs operations on bytes with one seeded `random.Random`. `OPERATIONS` lists every type and its parameters; adding an operation means an entry there, a function in `byte_ops.py`, and help text in the CLI.
- `media.py` — line mode: `media` class splits the lines into header and body, exposes `glitch_random_swap(interval, flavour)` and `glitch_corrupt(interval, flavour)`, then `text()`.
- `byte_ops.py` — byte mode operations; each edits a bytearray in place, skips the header bytes, keeps the length.
- `presets.py` — load/validate/save/apply presets; no CLI dependency, safe to import elsewhere.
- `presets/` — preset JSON files. `default` is what runs with no operations.
- `tests/` — `python3 -m unittest discover -s tests`.
- `examples/` — sample outputs referenced by the README.

## Conventions and gotchas
- `header_length` (lines, line mode) and `header_bytes` (byte mode) are kept untouched so the file stays openable. Glitching the header just breaks the file.
- Line mode output must stay byte-identical; the golden tests check this. Consecutive line operations share one line split, and line operations must draw randomness in the same order as before.
- Saved "good settings" are JSON files in `presets/` (format in `presets.py`) — keep them, and add new good ones rather than deleting. Use `--save-preset` to create one.
- Files are read in text mode line by line, so output is meant to be lossy and unpredictable. Not a bug.
- `.gitignore` ignores `__pycache__/`, `*.pyc` and `.DS_Store`.
- Style: comment blocks above each method, double-underscore private helpers.

## Git workflow
- Never commit directly to `master`. Before making any commit, create a branch named for the work (e.g. `feature/add-glitch-mode`, `fix/header-parsing`, `docs/update-notes`) and commit there.
- If you're on `master` when asked to commit, switch to a new branch first.
- Keep commits small and focused, with a short imperative message.
- Pushing to a branch Claude created is fine without asking. Ask before force-pushing or pushing to any other branch (including `master`).
- Open a PR without asking once the work on a branch Claude created is done (tests pass, docs updated). For any other branch, ask first. Don't merge PRs.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
