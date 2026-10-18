# Media-Glitcher
for python 3

## Usage
```
python3 media_glitcher.py input_file output_file [options]
```

Options:

 * `--swap INTERVAL,FLAVOUR` / `--corrupt INTERVAL,FLAVOUR` add a glitch operation. Both are repeatable and run in the order given.
 * `--preset recommended|classic` adds a named group of operations.
 * `--header-length LINES` lines left untouched (default 15, good for video; images may be fine with 0).
 * `--seed N` makes the output reproducible.
 * `-q` / `--quiet` suppresses the file name output.

With no operations given it runs `--corrupt 5000,8 --swap 820,3`. See `-h` for details.

## Some Recommended Settings
These settings have gotten good results on their own and together (also available as `--preset recommended`):
```
python3 media_glitcher.py in.avi out.avi --swap 200,50 --swap 100,3 --corrupt 200,30 --corrupt 400,3 --swap 40,3
```

## Examples
When used on images:

<img src="examples/lightning-glitched.jpg" alt="lightning" width="250">

<img src="examples/confetti-glitched.jpg" alt="confetti" width="250">

When used on video:

<img src="examples/gif-glitched-waves.gif" alt="gif-waves" width="250">