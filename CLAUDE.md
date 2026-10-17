# Media-Glitcher

Small Python 2.7 tool that glitches media files (images, video) by swapping and corrupting lines of the raw file text. Personal/art project; no tests.

## Run
```
python2.7 media_glitcher.py input_file output_file
```
- Python 2 only (uses `print` statements). Don't port to Python 3 or add py3-only syntax unless asked.
- `python2.7` may not be installed locally, so check before trying to run it.

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
- Keep commits small and focused, with a short imperative message. Don't push or open a PR unless asked.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
