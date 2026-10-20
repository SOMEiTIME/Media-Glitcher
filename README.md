# Media-Glitcher
for python 3

## Usage
```
python3 media_glitcher.py input_file output_file [options]
```

Four modes, mix them in one run:

 * **Line mode**: swaps and corrupts "lines" (split at newline bytes). Random lengths, so unpredictable results.
 * **Byte mode**: exact byte positions and sizes, so you control the damage.
 * **Frame mode**: datamoshes MPEG-4 AVI video.
 * **Pixel mode**: pixel sorts images.

Operations run in the order given, and can be repeated. With none given, the `default` preset runs. `-h` has the details.

### Line mode
 * `--swap INTERVAL,FLAVOUR`
 * `--corrupt INTERVAL,FLAVOUR`
 * `--header-length LINES` lines left alone (default 15, good for video, images may be fine with 0)

### Byte mode
 * `--byte-swap SIZE,EVERY` swap a SIZE-byte chunk with a nearby one, once every EVERY bytes
 * `--byte-corrupt EVERY` random value for one byte, once every EVERY bytes
 * `--bitflip RATE` fraction of bits to flip, `0.0001` is one in ten thousand
 * `--repeat SIZE,EVERY` copy a SIZE-byte chunk over the next one, once every EVERY bytes
 * `--header-bytes BYTES` bytes left alone (default 1024)
 * `--target TARGET` which part of the file to change (see below). `all` is the default, `auto` picks by file type

### Frame mode (MPEG-4 AVI only)
 * `--iframe-drop KEEP` keep the first KEEP keyframes, remove the rest
 * `--pframe-repeat EVERY,COUNT` every EVERY frames, repeat a P-frame COUNT more times

### Pixel mode (images)
 * `--pixel-sort KEY,LOW,HIGH,ANGLE` sort runs of pixels whose KEY is from LOW to HIGH (0 to 1) by that key, along lines at ANGLE degrees

See [Pixel sort](#pixel-sort).

### Other
 * `--preset NAME_OR_FILE` add a preset's operations
 * `--save-preset NAME_OR_FILE [--description TEXT]` save this run as a preset (`--force` to overwrite)
 * `--list-presets`
 * `--seed N` reproducible output
 * `-q` quiet

## Datamosh
Dropping a keyframe makes the following P-frames apply their motion to the old picture. Repeating a P-frame smears it. Audio is untouched and the index is dropped (players rebuild it). Try `--preset datamosh`.

To push a still image around with a clip's motion, make an AVI of the still followed by the clip, with a keyframe at the cut only, then drop it:
```
ffmpeg -loop 1 -framerate 10 -t 0.5 -i still.png -i clip.mp4 \
  -filter_complex "[0:v]setsar=1[a];[1:v]scale=W:H,setsar=1[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -c:v mpeg4 -g 9999 -bf 0 -force_key_frames 0.5 -r 10 -an in.avi
python3 media_glitcher.py in.avi out.avi --iframe-drop 1
```
`W:H` is the still's size, `0.5` its length in seconds. Keep `-bf 0`, B-frames make it unpredictable.

`--target avi-frames` points byte operations at the video frames only, so they don't break the file's structure. Use it when mixing byte and frame operations.

Other video (H.264 MP4s etc.) is refused. Convert first: `ffmpeg -i in.mp4 -c:v mpeg4 -bf 0 in.avi`

## Pixel sort
Pixels whose key is inside the threshold get sorted, darkest (or lowest) first, in unbroken runs along each line. Pixels outside it stay put and break the runs, so you get streaks, not a smear.

 * KEY: `brightness`, `hue`, `saturation`, `r`, `g` or `b`
 * LOW, HIGH: `0.25,0.8` sorts the midtones. `0,1` sorts whole lines
 * ANGLE: `0` left to right, `90` top to bottom, `180` right to left (reversed), anything in between for diagonals

```
python3 media_glitcher.py in.jpg out.jpg --pixel-sort brightness,0.25,0.8,90
```
Needs NumPy (`pip install numpy`). PPM is read directly. JPEG, PNG and BMP go through `ffmpeg` and come back in the same format (PNG loses its transparency). It works on decoded pixels, so run it before byte operations, or the image will be broken. No randomness: `--seed` doesn't change it. Video isn't supported yet.

## Targets
Targets find the part of the file to change, so the rest stays intact.

 * `jpeg-scan`: image data only. Streaks and shifted rows, file stays openable. Try `--preset jpeg-streaks`.
 * `jpeg-tables`: quantization tables only. A texture over the whole image. Tables are tiny, so use small spacings (`--byte-corrupt 16`) or high rates (`--bitflip 0.1`). Try `--preset jpeg-texture`.
 * `bmp-pixels`, `ppm-pixels`: raw pixels of uncompressed BMP, PPM/PGM/PBM.
 * `wav-samples`, `aiff-samples`: raw audio. Keep `--repeat` and `--byte-swap` sizes a multiple of 24 for clean stutters, other sizes are loud noise. Try `--preset audio-stutter`.
 * `avi-frames`: see above.

Compressed variants (RLE BMP, ADPCM WAV, etc.) are refused. `--target auto` picks one by file type, or `all` if it doesn't know.

## What files to glitch
"Tested" means I glitched it with lots of seeds and checked macOS or Pillow still opens it.

| Format | How it reacts | Status |
|---|---|---|
| JPEG | Streaks, shifted rows, colour bands. Use the JPEG targets. | Tested |
| BMP, TIFF (uncompressed) | Always opens. Needs heavy settings, try `--preset bytes-uncompressed`. | Tested |
| PNG | Opens, then goes black at the first damage (compressed and checksummed). | Tested |
| PPM/PGM/PBM | Like BMP. | Tested |
| WAV, AIFF | Clicks, stutters, repeats. | Tested |
| AVI (Xvid/MPEG-4) | Classic video target. Frame mode and `avi-frames` datamosh it. | Lightly tested |
| MP4/MOV | Players often refuse them. Convert to AVI first. | Expected |
| GIF | Compressed, so damage tends to cut it off like PNG. | Expected |
| HEIC | Not supported. Export as JPEG. | Not planned |

## Presets
JSON file for a whole run: operations in order, plus optional `header_length`, `header_bytes`, `target`, `seed` and `description`. A bare name is looked up in `presets/`, anything with a `/` or `.json` is a path.
```json
{
  "description": "Heavy glitching for video",
  "header_length": 15,
  "seed": 42,
  "operations": [
    {"type": "swap", "interval": 200, "flavour": 50},
    {"type": "byte-swap", "size": 64, "every": 5000},
    {"type": "bitflip", "rate": 0.0001}
  ]
}
```
```
python3 media_glitcher.py in.avi out.avi --preset recommended
python3 media_glitcher.py in.avi out.avi --swap 200,50 --corrupt 200,30 --save-preset mine
```
Command line options override the preset's `header_length`, `header_bytes`, `target` and `seed`. A preset with a `seed` always gives the same output.

`recommended` has the settings that worked well on their own and together. It's also split into `swaps-sparse`, `swaps-frequent` and `corrupt-escalating`, so you can combine them (`--preset swaps-frequent --preset corrupt-escalating`). All three runs the same operations in a different order, so the result differs.

`presets.py` and `engine.py` don't depend on the CLI, so you can import them: `presets.load()`, `engine.glitch(data, operations, ...)`.

## Tests
```
python3 -m unittest discover -s tests
```
`tests/cases.json` has golden-output cases (seeded preset, generated input, expected SHA-256). If glitch behaviour changes on purpose, run `python3 tests/test_golden.py --update` and review the diff. Hashes can change between Python versions.

## Examples
When used on images:

<img src="examples/lightning-glitched.jpg" alt="lightning" width="250">

<img src="examples/confetti-glitched.jpg" alt="confetti" width="250">

When used on video:

<img src="examples/gif-glitched-waves.gif" alt="gif-waves" width="250">
