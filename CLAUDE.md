# Media-Glitcher

Small Python 3 tool that glitches media files (images, video) by swapping and corrupting lines of the raw file text. Personal/art project; tests are in `tests/`.

## Run
```
python3 media_glitcher.py input_file output_file [--swap I,F] [--corrupt I,F] [--preset NAME_OR_FILE] [--save-preset NAME_OR_FILE] [--header-length N] [--seed N]
python3 media_glitcher.py --list-presets
```
- Python 3 (ported from 2.7). Files are opened as latin-1 so binary data round-trips byte for byte.
- Don't run it on files in `examples/`; the output path gets overwritten.

## Layout
- `media_glitcher.py` — argparse CLI. Glitch operations come from `--swap`/`--corrupt`/`--preset` flags (run in order given). Saved "good settings" are presets, not code.
- `media.py` — `media` class: splits the file into header and body lines, exposes `glitch_random_swap(interval, flavour)` and `glitch_corrupt(interval, flavour)`, then `print_to_new_file()`.
- `presets.py` — load/validate/save/apply presets; no CLI dependency, safe to import elsewhere.
- `presets/` — preset JSON files. `default` is what runs with no operations.
- `tests/` — `python3 -m unittest discover -s tests`.
- `examples/` — sample outputs referenced by the README.

## Conventions and gotchas
- `header_length` (lines) is kept untouched so the file stays openable. 15 works for video, 0 is fine for images. Glitching the header just breaks the file.
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
- Before opening a PR, do a final pass over the whole diff against `master`: is it readable, well designed, and no more verbose than it needs to be? Fix what you find, without changing behaviour, then re-run the tests (`python3 -m unittest discover -s tests`) and note what the pass changed in the PR description.
- Stage specific files (not `git add -A`), since stray files like `.DS_Store` are lying around.
