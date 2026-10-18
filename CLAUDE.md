# Media-Glitcher

Small Python 3 tool that glitches media files (images, video) by swapping and corrupting lines of the raw file text. Personal/art project; no tests.

## Run
```
python3 media_glitcher.py input_file output_file [--swap I,F] [--corrupt I,F] [--preset NAME] [--header-length N] [--seed N]
```
- Python 3 (ported from 2.7). Files are opened as latin-1 so binary data round-trips byte for byte.
- Don't run it on files in `examples/`; the output path gets overwritten.

## Layout
- `media_glitcher.py` — argparse CLI. Glitch operations come from `--swap`/`--corrupt`/`--preset` flags (run in order given); `DEFAULT_OPERATIONS` and `PRESETS` at the top hold the saved "good settings".
- `media.py` — `media` class: splits the file into header and body lines, exposes `glitch_random_swap(interval, flavour)` and `glitch_corrupt(interval, flavour)`, then `print_to_new_file()`.
- `examples/` — sample outputs referenced by the README.

## Conventions and gotchas
- `header_length` (lines) is kept untouched so the file stays openable. 15 works for video, 0 is fine for images. Glitching the header just breaks the file.
- Saved "good settings" live in `PRESETS` in `media_glitcher.py` — keep them, and add new good ones rather than deleting.
- Files are read in text mode line by line, so output is meant to be lossy and unpredictable. Not a bug.
- `.gitignore` is allowlist-style (`*`, then `!py`, `!md`), and those entries don't look like real extension patterns. If a new file doesn't show up in `git status`, check the ignore rules or use `git add -f`.
- Style: comment blocks above each method, double-underscore private helpers.

## Git workflow
- Never commit directly to `master`. Before making any commit, create a branch named for the work (e.g. `feature/add-glitch-mode`, `fix/header-parsing`, `docs/update-notes`) and commit there.
- If you're on `master` when asked to commit, switch to a new branch first.
- Keep commits small and focused, with a short imperative message. Don't push or open a PR unless asked.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
