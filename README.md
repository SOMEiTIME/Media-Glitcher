# Media-Glitcher
for python 3

## Usage
```
python3 media_glitcher.py input_file output_file [options]
```

There are three modes, and you can mix them in one run:

 * **Line mode** (the original): splits the file wherever a newline byte happens to be, then swaps "lines". Lines in binary data have random lengths, so results are unpredictable, which is part of the charm.
 * **Byte mode**: works on exact byte positions and sizes, so the amount and spacing of damage is under your control.
 * **Frame mode**: datamoshes MPEG-4 AVI video by removing or repeating whole frames (see below).

Line mode options:

 * `--swap INTERVAL,FLAVOUR` / `--corrupt INTERVAL,FLAVOUR` add a line operation.
 * `--header-length LINES` lines left untouched (default 15, good for video; images may be fine with 0).

Byte mode options:

 * `--byte-swap SIZE,EVERY` swaps a SIZE-byte chunk with a nearby one, once every EVERY bytes.
 * `--byte-corrupt EVERY` replaces one byte with a random value, once every EVERY bytes.
 * `--bitflip RATE` flips that fraction of bits, e.g. `0.0001` is one bit in ten thousand.
 * `--repeat SIZE,EVERY` copies a SIZE-byte chunk over the next one, once every EVERY bytes (smears and stutters).
 * `--header-bytes BYTES` bytes left untouched (default 1024, which keeps most file signatures and basic headers).
 * `--target TARGET` chooses which part of the file byte operations change (see below). The default, `all`, is everything after `--header-bytes`; `auto` picks a target from the file type.

Frame mode options (AVI with MPEG-4 part 2 video only):

 * `--iframe-drop KEEP` keeps the first KEEP keyframes and removes all the rest.
 * `--pframe-repeat EVERY,COUNT` once every EVERY video frames, repeats a P-frame COUNT more times.

Every operation is repeatable, and they all run in the order given. Other options:

 * `--preset NAME_OR_FILE` adds the operations from a preset (see below).
 * `--seed N` makes the output reproducible.
 * `--save-preset NAME_OR_FILE [--description TEXT]` saves this run's settings as a preset. It won't replace an existing preset unless you add `--force`, and it always prints where it saved, even with `-q`.
 * `--list-presets` lists the available presets.
 * `-q` / `--quiet` suppresses the file name output.

With no operations given it uses the `default` preset. See `-h` for details.

## Datamosh (video)
A keyframe holds a whole picture; the P-frames after it only hold motion vectors and changes. `--iframe-drop` removes keyframes, so the next P-frames apply their motion to whatever picture came before. `--pframe-repeat` replays a P-frame's motion several times, so the picture smears and blooms. Audio is left alone, and the index is dropped so players rebuild it. Try `--preset datamosh`.

To move a still image with a clip's motion, encode the image followed by the clip with a keyframe at the cut and none elsewhere, then drop that one:
```
ffmpeg -loop 1 -framerate 10 -t 0.5 -i still.png -i clip.mp4 \
  -filter_complex "[0:v]setsar=1[a];[1:v]scale=W:H,setsar=1[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -c:v mpeg4 -g 9999 -bf 0 -force_key_frames 0.5 -r 10 -an in.avi
python3 media_glitcher.py in.avi out.avi --iframe-drop 1
```
(`W:H` is the still's size, and `0.5` the still's length in seconds.) Use `-bf 0`: B-frames reference frames out of order, which makes the result unpredictable.

`--target avi-frames` (also picked by `--target auto`) points byte operations at the compressed video frames only, so `--bitflip` or `--byte-corrupt` damage the picture without breaking the file's structure. Use it when mixing: byte operations on the default `all` target can hit a chunk header, and a frame operation after that refuses the file.

Anything that isn't an MPEG-4 part 2 AVI (H.264 MP4s, for instance) is refused with an error. Convert first, e.g. `ffmpeg -i in.mp4 -c:v mpeg4 -bf 0 in.avi`. Dropping a keyframe in H.264 is a different job and isn't supported.

## JPEG targets
Plain byte mode can hit a JPEG's headers, tables and metadata as easily as its pixels, which is why it sometimes breaks the file. The JPEG targets read the file's structure and only change one part:

 * `--target jpeg-scan` changes only the compressed image data, never leaving a byte that would end it early. Headers, tables, metadata (including the thumbnail) and the extra images iPhones append stay untouched. You get streaks and shifted rows, and the file keeps its structure. Try `--preset jpeg-streaks`.
 * `--target jpeg-tables` changes only the quantization tables, which set how coarsely detail is stored. You get a texture over the whole image, from a fine weave (`--preset jpeg-texture`) to bold block patterns (`--preset jpeg-texture-heavy`). The tables are tiny, so use small spacings like `--byte-corrupt 16` or high rates like `--bitflip 0.1`.

Tested on baseline, progressive, restart-marker and iPhone-style JPEGs and a photo (600 runs per target): with `jpeg-scan` libjpeg decoded all of them and macOS opened 598 (both misses were progressive), against 502 with `all`. `jpeg-tables` decoded every time without a warning.

## Uncompressed targets
These targets find the raw pixels or samples from the file's own header, instead of guessing with `--header-bytes`. The header, a BMP's colour palette, and anything stored after the data (colour profiles, metadata chunks) stay untouched.

 * `--target bmp-pixels`: uncompressed BMPs (1, 8, 24 and 32 bit).
 * `--target ppm-pixels`: binary PPM, PGM and PBM.
 * `--target wav-samples` and `--target aiff-samples`: uncompressed WAV, AIFF and AIFF-C (integer or float samples).

Compressed variants (RLE BMPs, ADPCM or u-law WAVs, IMA4 AIFF-C) are refused with an error rather than damaged blindly. `--target auto` picks the right one of these, or a JPEG target, from the file's first bytes, and falls back to `all` for other files.

For audio, keep `--repeat` and `--byte-swap` sizes a multiple of 24 bytes: samples then stay aligned and you get clean stutters, while other sizes turn into loud noise. Try `--preset audio-stutter` or `--preset audio-crackle`.

## What files to glitch
How a format stores its data decides how it reacts. "Tested" means glitched with many seeds and checked that macOS (or Pillow) can still decode it; the rest is what to expect from how the format works, not yet tried.

| Format | How it reacts | Status |
|---|---|---|
| JPEG | Small byte changes spread into horizontal streaks, shifted rows and colour bands. Use the JPEG targets above to keep the file intact. | Tested |
| BMP, uncompressed TIFF | Always opened. Damage stays where you put it (shifted bands, speckle), so it needs much heavier settings: try `--preset bytes-uncompressed`, with `--target bmp-pixels` for BMPs. Light settings are invisible. | Tested |
| PNG | Opens, but the image goes black from the first damaged spot, because the pixels are compressed and checksummed. A PNG-aware mode is planned. | Tested |
| PPM/PGM/PBM | Like BMP: raw pixels after a tiny header. Use `--target ppm-pixels`. | Tested |
| WAV, AIFF | Raw audio: clicks, stutters and repeats. Use `--target auto` and sizes that are multiples of 24 (see above). | Tested |
| AVI (Xvid/MPEG-4) | The classic target for video glitching; the `gif-glitched-waves` example came from line mode on video. Frame mode and `avi-frames` datamosh it (see above). | Lightly tested (ffmpeg decodes the output) |
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