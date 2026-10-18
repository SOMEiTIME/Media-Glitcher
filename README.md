# Media-Glitcher
for python 3

## Usage
```
python3 media_glitcher.py input_file output_file [options]
```

There are two modes, and you can mix them in one run:

 * **Line mode** (the original): splits the file wherever a newline byte happens to be, then swaps "lines". Lines in binary data have random lengths, so results are unpredictable, which is part of the charm.
 * **Byte mode**: works on exact byte positions and sizes, so the amount and spacing of damage is under your control.

Line mode options:

 * `--swap INTERVAL,FLAVOUR` / `--corrupt INTERVAL,FLAVOUR` add a line operation.
 * `--header-length LINES` lines left untouched (default 15, good for video; images may be fine with 0).

Byte mode options:

 * `--byte-swap SIZE,EVERY` swaps a SIZE-byte chunk with a nearby one, once every EVERY bytes.
 * `--byte-corrupt EVERY` replaces one byte with a random value, once every EVERY bytes.
 * `--bitflip RATE` flips that fraction of bits, e.g. `0.0001` is one bit in ten thousand.
 * `--repeat SIZE,EVERY` copies a SIZE-byte chunk over the next one, once every EVERY bytes (smears and stutters).
 * `--header-bytes BYTES` bytes left untouched (default 1024, which keeps most file signatures and basic headers).
 * `--target all|jpeg-scan|jpeg-tables` chooses which part of the file byte operations change (see below). The default, `all`, is everything after `--header-bytes`.

Every operation is repeatable, and they all run in the order given. Other options:

 * `--preset NAME_OR_FILE` adds the operations from a preset (see below).
 * `--seed N` makes the output reproducible.
 * `--save-preset NAME_OR_FILE [--description TEXT]` saves this run's settings as a preset. It won't replace an existing preset unless you add `--force`, and it always prints where it saved, even with `-q`.
 * `--list-presets` lists the available presets.
 * `-q` / `--quiet` suppresses the file name output.

With no operations given it uses the `default` preset. See `-h` for details.

## JPEG targets
Plain byte mode can hit a JPEG's headers, tables and metadata as easily as its pixels, which is why it sometimes breaks the file. The JPEG targets read the file's structure and only change one part:

 * `--target jpeg-scan` changes only the compressed image data, never leaving a byte that would end it early. Headers, tables, metadata (including the thumbnail) and the extra images iPhones append stay untouched. You get streaks and shifted rows, and the file keeps its structure. Try `--preset jpeg-streaks`.
 * `--target jpeg-tables` changes only the quantization tables, which set how coarsely detail is stored. You get a texture over the whole image, from a fine weave (`--preset jpeg-texture`) to bold block patterns (`--preset jpeg-texture-heavy`). The tables are tiny, so use small spacings like `--byte-corrupt 16` or high rates like `--bitflip 0.1`.

Tested on baseline, progressive, restart-marker and iPhone-style JPEGs and a photo (600 runs per target): with `jpeg-scan` libjpeg decoded all of them and macOS opened 598 (both misses were progressive), against 502 with `all`. `jpeg-tables` decoded every time without a warning.

## What files to glitch
How a format stores its data decides how it reacts. "Tested" means glitched with five seeds and checked that macOS can still decode it; the rest is what to expect from how the format works, not yet tried.

| Format | How it reacts | Status |
|---|---|---|
| JPEG | Small byte changes spread into horizontal streaks, shifted rows and colour bands. Use the JPEG targets above to keep the file intact. | Tested |
| BMP, uncompressed TIFF | Always opened. Damage stays where you put it (shifted bands, speckle), so it needs much heavier settings: try `--preset bytes-uncompressed`. Light settings are invisible. | Tested |
| PNG | Opens, but the image goes black from the first damaged spot, because the pixels are compressed and checksummed. A PNG-aware mode is planned. | Tested |
| PPM/PGM | Like BMP: raw pixels after a tiny header. | Expected |
| WAV, AIFF | Raw audio after the header: clicks, stutters and repeats. Keep `--header-bytes` at least 44 for WAV. | Expected |
| AVI (Xvid/MPEG-4) | The classic target for video glitching; the `gif-glitched-waves` example came from line mode on video. | Expected |
| MP4/MOV (iPhone video) | Players often refuse damaged files. Convert to AVI first. | Expected |
| GIF | Compressed (LZW), so damage tends to cut the image off, like PNG. | Expected |
| HEIC (iPhone photos) | Not supported. Set the camera to "Most Compatible" or export as JPEG. | Not planned |

## Presets
A preset is a JSON file for a whole run: the operations in order, plus optional `header_length`, `header_bytes`, `target`, `seed` and `description`.
A bare name is looked up in `presets/`; anything with a `/` or `.json` is treated as a path.
```json
{
  "description": "Heavy glitching for video",
  "header_length": 15,
  "seed": 42,
  "operations": [
    {"type": "swap", "interval": 200, "flavour": 50},
    {"type": "corrupt", "interval": 200, "flavour": 30},
    {"type": "byte-swap", "size": 64, "every": 5000},
    {"type": "bitflip", "rate": 0.0001}
  ]
}
```
```
python3 media_glitcher.py in.avi out.avi --preset recommended
python3 media_glitcher.py in.avi out.avi --swap 200,50 --corrupt 200,30 --save-preset mine
```
Options on the command line override a preset's `header_length`, `header_bytes`, `target` and `seed`. A preset with a `seed` gives identical output every run, which makes presets usable as test cases.
`presets.py` and `engine.py` have no CLI dependencies, so other programs can load presets with `presets.load()` and run them with `engine.glitch(data, operations, ...)`.

`--list-presets` lists them. `recommended` holds the settings that have worked well on their own and together (five operations). It's also split into three smaller presets, `swaps-sparse`, `swaps-frequent` and `corrupt-escalating`, so you can use one or a few at a time, e.g. `--preset swaps-frequent --preset corrupt-escalating`. Using all three runs the same operations as `recommended`, but in a different order, so the result differs.

## Tests
```
python3 -m unittest discover -s tests
```
`tests/cases.json` holds golden-output cases: a seeded `test-*` preset, a generated input, and the expected SHA-256 of the result. If glitch behaviour changes on purpose, regenerate the hashes with `python3 tests/test_golden.py --update` and review the diff. Hashes depend on Python's `random`, so they may need regenerating on a different Python version.

## Examples
When used on images:

<img src="examples/lightning-glitched.jpg" alt="lightning" width="250">

<img src="examples/confetti-glitched.jpg" alt="confetti" width="250">

When used on video:

<img src="examples/gif-glitched-waves.gif" alt="gif-waves" width="250">