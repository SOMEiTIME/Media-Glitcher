# Media-Glitcher
for python 3

## Usage
```
python3 media_glitcher.py input_file output_file [options]
```

Options:

 * `--swap INTERVAL,FLAVOUR` / `--corrupt INTERVAL,FLAVOUR` add a glitch operation. Both are repeatable and run in the order given.
 * `--preset NAME_OR_FILE` adds the operations from a preset (see below).
 * `--header-length LINES` lines left untouched (default 15, good for video; images may be fine with 0).
 * `--seed N` makes the output reproducible.
 * `--save-preset NAME_OR_FILE [--description TEXT]` saves this run's settings as a preset.
 * `--list-presets` lists the available presets.
 * `-q` / `--quiet` suppresses the file name output.

With no operations given it uses the `default` preset. See `-h` for details.

## Presets
A preset is a JSON file for a whole run: the operations in order, plus optional `header_length`, `seed` and `description`.
A bare name is looked up in `presets/`; anything with a `/` or `.json` is treated as a path.
```json
{
  "description": "Heavy glitching for video",
  "header_length": 15,
  "seed": 42,
  "operations": [
    {"type": "swap", "interval": 200, "flavour": 50},
    {"type": "corrupt", "interval": 200, "flavour": 30}
  ]
}
```
```
python3 media_glitcher.py in.avi out.avi --preset recommended
python3 media_glitcher.py in.avi out.avi --swap 200,50 --corrupt 200,30 --save-preset mine
```
Options on the command line override a preset's `header_length` and `seed`. A preset with a `seed` gives identical output every run, which makes presets usable as test cases.
`presets.py` has no CLI dependencies, so other programs can `import presets` to load, validate and apply them.

`--list-presets` lists them. `recommended` holds the settings that have worked well on their own and together (five operations). It's also split into three smaller presets, `swaps-sparse`, `swaps-frequent` and `corrupt-escalating`, so you can use one or a few at a time, e.g. `--preset swaps-frequent --preset corrupt-escalating`. Using all three runs the same operations as `recommended`, but in a different order, so the result differs.

## Tests
```
python3 -m unittest discover -s tests
```

## Examples
When used on images:

<img src="examples/lightning-glitched.jpg" alt="lightning" width="250">

<img src="examples/confetti-glitched.jpg" alt="confetti" width="250">

When used on video:

<img src="examples/gif-glitched-waves.gif" alt="gif-waves" width="250">