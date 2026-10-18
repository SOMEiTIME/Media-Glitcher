# Media-Glitcher

Small Python 3 tool that glitches media files (images, video) by swapping and corrupting lines of the raw file text. Personal/art project; no tests.

## Run
```
python3 media_glitcher.py input_file output_file
```
- Python 3 (ported from 2.7). Files are opened as latin-1 so binary data round-trips byte for byte.
- Don't run it on files in `examples/`; the output path gets overwritten.

## Layout
- `media_glitcher.py` — entry point and the customization area. Glitch operations are listed (and commented in/out) here; edit this to change the effect.
- `media.py` — `media` class: splits the file into header and body lines, exposes `glitch_random_swap(interval, flavour)` and `glitch_corrupt(interval, flavour)`, then `print_to_new_file()`.
- `examples/` — sample outputs referenced by the README.

## Conventions and gotchas
- `header_length` (lines) is kept untouched so the file stays openable. 15 works for video, 0 is fine for images. Glitching the header just breaks the file.
- Commented-out glitch calls in `media_glitcher.py` are saved "good settings" — keep them, and add new good ones rather than deleting.
- Files are read in text mode line by line, so output is meant to be lossy and unpredictable. Not a bug.
- `.gitignore` is allowlist-style (`*`, then `!py`, `!md`), and those entries don't look like real extension patterns. If a new file doesn't show up in `git status`, check the ignore rules or use `git add -f`.
- Style: comment blocks above each method, double-underscore private helpers.

## Git workflow
- Never commit directly to `master`. Before making any commit, create a branch named for the work (e.g. `feature/add-glitch-mode`, `fix/header-parsing`, `docs/update-notes`) and commit there.
- If you're on `master` when asked to commit, switch to a new branch first.
- Keep commits small and focused, with a short imperative message.
- Pushing to a branch Claude created is fine without asking. Ask before force-pushing, pushing to any other branch (including `master`), or opening a PR.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
