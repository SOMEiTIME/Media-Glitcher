#!/usr/bin/env python3

# Text preview of a glitched file, for --preview: the picture drawn with a
# repeating word, shaded in greys by brightness, with the damage (where the
# output differs from the input) picked out in red, case swapped so it still
# shows without colour.
#
# BMP and PPM are read directly, so their damage is exact to the pixel. Other
# images and video go through ffmpeg at terminal size, and video plays in place
# until it ends or Ctrl-C. Anything without a picture, or without ffmpeg, gets
# a map of the file's bytes instead, one cell per chunk.
#
# Stdlib only, and no random draws, so it never changes the glitched output.

import os, shutil, subprocess, time
import uncompressed

FPS = 12                 # video playback rate
DEFAULT_WORD = "GLTCHR"  # when the file name has nothing printable, or the output name was defaulted
GREYS = range(232, 256)  # xterm 256-colour greys, dark to light
REDS = (52, 88, 124, 160, 196, 203, 210, 217, 224, 231)  # dark red to white, for damage
CAPTION = 244            # grey of the line under the picture
DARK = 24                # undamaged cells darker than this are left blank
THRESHOLD = 16           # grey levels a cell must change by to count as damaged (ffmpeg path)
WINDOW = 8               # input frames searched for the one an output frame came from
SAMPLES = 3              # points per side averaged for a cell's brightness (BMP, PPM)
MAP_ROWS = 8             # height of the byte map

#
# The word to draw with: printable ASCII from text without spaces (wider
# characters would break the grid), followed by a space, or DEFAULT_WORD
#
def clean_word(text):
    word = "".join(c for c in text if " " < c <= "~")
    return (word or DEFAULT_WORD) + " "

# the default word: the output file's name without its extension
def word_for(path):
    return clean_word(os.path.splitext(os.path.basename(path))[0])

#
# Prints the preview of output_path (glitched from input_path) to out. size is
# the terminal size (os.terminal_size); color adds ANSI colours, animate plays
# video in place (otherwise only its first frame is printed)
#
def show(input_path, output_path, out, word=None, size=None, color=True, animate=True):
    word = clean_word(word) if word else word_for(output_path)
    size = size or shutil.get_terminal_size()
    columns, rows = max(1, size.columns - 1), max(1, size.lines - 2)  # room for the caption and the prompt
    name = os.path.basename(output_path)
    with open(input_path, "rb") as f:
        before = f.read()
    with open(output_path, "rb") as f:
        after = f.read()

    layout = _raw_layout(after)
    if layout:
        width, grey, damage = _raw_frame(before, after, layout, columns, rows)
        _write(out, render(grey, damage, width, word, color=color), _caption(name, damage), color)
        return
    frames, originals = _ffmpeg_frames(output_path, columns, rows), _ffmpeg_frames(input_path, columns, rows)
    try:
        first = next(frames, None)
    except OSError:
        first = None  # no ffmpeg
    if first:
        _play(out, first, frames, originals, word, name, color, animate)
    else:
        frames.close()
        width, grey, damage = _byte_map(before, after, columns, min(rows, MAP_ROWS))
        _write(out, render(grey, damage, width, word, color=color), _caption(name + "  byte map", damage), color)

#
# Draws a picture as lines of text. grey has one brightness (0-255) per cell,
# width cells to a line; damage, if given, marks the damaged cells. The word
# runs on through every cell, starting offset letters in, and blank cells
# skip their letter, so the picture is cut out of one long text
#
def render(grey, damage, width, word, offset=0, color=True):
    lines = []
    for start in range(0, len(grey), width):
        line, last = [], None
        for i in range(start, min(start + width, len(grey))):
            char, level = word[(i + offset) % len(word)], grey[i]
            if damage and damage[i]:
                style, char = REDS[level * len(REDS) // 256], char.swapcase()
            elif level < DARK:
                style, char = last, " "  # a space needs no colour of its own
            else:
                style = GREYS[level * len(GREYS) // 256]
            if color and style != last:
                line.append("\x1b[38;5;%dm" % style)
                last = style
            line.append(char)
        lines.append("".join(line) + ("\x1b[0m" if color and last else ""))
    return lines

# the line under the picture: the file name, and how much of it is damaged
def _caption(name, damage, frame=None):
    parts = [name] + ([] if frame is None else ["frame %d" % frame])
    if damage is not None:
        parts.append("%d%% damaged" % round(100 * sum(damage) / max(1, len(damage))))
    return "  ".join(parts)

# writes the picture and its caption, and returns how many lines that took
def _write(out, lines, caption, color):
    out.write("\n".join(lines + [("\x1b[38;5;%dm%s\x1b[0m" % (CAPTION, caption)) if color else caption]) + "\n")
    out.flush()
    return len(lines) + 1

# the columns and rows of a grid for a width x height picture; a cell is about twice as tall as it's wide
def _grid(width, height, columns, rows):
    columns = max(1, min(columns, width, round(rows * 2 * width / height)))
    return columns, max(1, min(height, round(columns * height / width / 2)))

#
# Where an uncompressed picture's pixels are: (start, width, height, bytes per
# row, bytes per pixel, offsets of red, green and blue in a pixel, stored
# bottom up), or None if it isn't a 24 or 32-bit BMP or an 8 or 16-bit PGM or PPM
#
def _raw_layout(data):
    try:
        if data[:2] == b"BM":
            uncompressed.bmp_pixels(data)  # checks the pixels are all there
            start, width, height, bits, stride = uncompressed.bmp_header(data)
            if bits not in (24, 32) or width <= 0:
                return None
            return start, width, abs(height), stride, bits // 8, (2, 1, 0), height > 0
        if data[:2] in (b"P5", b"P6"):
            uncompressed.ppm_pixels(data)  # checks the pixels are all there
            kind, (width, height, maxval), start = uncompressed.ppm_header(data)
            size = 2 if maxval > 255 else 1  # 16-bit samples are big-endian, so offset 0 is the high byte
            channels = 3 if kind == b"P6" else 1
            offsets = (0, size, 2 * size) if channels == 3 else (0, 0, 0)
            return start, width, height, width * channels * size, channels * size, offsets, False
    except uncompressed.FormatError:
        pass
    return None

#
# Samples a BMP or PPM down to a grid: (columns, brightness per cell, damage
# per cell). A cell is damaged if any byte of its pixels changed, so even a
# single corrupted pixel shows. No damage (None) if the input's layout differs
#
def _raw_frame(before, after, layout, columns, rows):
    start, width, height, stride, bpp, (r, g, b), flip = layout
    columns, rows = _grid(width, height, columns, rows)
    row_at = lambda y: start + (height - 1 - y if flip else y) * stride
    xs = [x * width // columns for x in range(columns + 1)]
    grey, damage = bytearray(columns * rows), bytearray(columns * rows)
    for cy in range(rows):
        y0, y1 = cy * height // rows, (cy + 1) * height // rows
        for y in range(y0, y1):
            pos = row_at(y)
            if before[pos:pos + stride] != after[pos:pos + stride]:
                for cx in range(columns):
                    a, z = pos + xs[cx] * bpp, pos + xs[cx + 1] * bpp
                    damage[cy * columns + cx] |= before[a:z] != after[a:z]
        for cx in range(columns):
            total = 0
            for sy in range(SAMPLES):
                pos = row_at(y0 + (y1 - y0) * (2 * sy + 1) // (2 * SAMPLES))
                for sx in range(SAMPLES):
                    p = pos + (xs[cx] + (xs[cx + 1] - xs[cx]) * (2 * sx + 1) // (2 * SAMPLES)) * bpp
                    total += 299 * after[p + r] + 587 * after[p + g] + 114 * after[p + b]  # Rec. 601 luma
            grey[cy * columns + cx] = total // (1000 * SAMPLES * SAMPLES)
    return columns, grey, damage if _raw_layout(before) == layout else None

#
# Decodes a file's video (or image) with ffmpeg, scaled to fit columns x rows
# cells and at FPS for video, and yields each frame as (columns, brightness per
# cell). Yields nothing if ffmpeg can't decode it; raises OSError without ffmpeg
#
def _ffmpeg_frames(path, columns, rows):
    scale = "scale='min(%d,%d*2*dar)':'max(1,ow/dar/2)':flags=area,format=gray" % (columns, rows)
    process = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "quiet", "-i", path, "-map", "0:v:0", "-vf", scale,
                                "-r", str(FPS), "-f", "image2pipe", "-c:v", "pgm", "pipe:1"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        # each frame is "P5\nW H\n255\n" and the pixels
        while True:
            header = [process.stdout.readline() for _ in range(3)]
            if not header[2]:
                return
            width, height = map(int, header[1].split())
            pixels = process.stdout.read(width * height)
            if len(pixels) < width * height:
                return
            yield width, pixels
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()

#
# Shows frames from ffmpeg, each against its input frame: an image once,
# video redrawn in place at FPS until it ends or Ctrl-C (only its first frame
# if not animated)
#
def _play(out, frame, frames, originals, word, name, color, animate):
    following = next(frames, None)
    video = following is not None
    animate = animate and video
    shown, n, began = 0, 0, time.monotonic()
    if animate:
        out.write("\x1b[?25l")  # hide the cursor while playing
    try:
        matcher = _Matcher(originals)
        while True:
            width, grey = frame
            damage = matcher.damage(grey)
            if shown:
                out.write("\x1b[%dA" % shown)  # back up to the top of the last frame
            lines = render(grey, damage, width, word, n, color)
            shown = _write(out, lines, _caption(name, damage, n + 1 if video else None), color)
            if not animate or following is None:
                break
            frame, following, n = following, next(frames, None), n + 1
            time.sleep(max(0, began + n / FPS - time.monotonic()))
    except KeyboardInterrupt:
        pass  # stops playback; the file is already written
    finally:
        if animate:
            out.write("\x1b[?25h")
            out.flush()
        frames.close()
        originals.close()

#
# Matches output frames to the input's as they play. Frame operations drop and
# repeat frames, so the output drifts out of step with the input; each output
# frame is compared with the closest of the next WINDOW input frames from the
# last match, so only what the glitch did shows as damage, not the drift
#
class _Matcher:
    def __init__(self, originals):
        self.originals, self.ahead = originals, []
        self.__fill()
        self.empty = not self.ahead  # the input can't be decoded, so there's nothing to compare with

    def __fill(self):
        while len(self.ahead) < WINDOW:
            frame = next(self.originals, None)
            if frame is None:
                break
            self.ahead.append(frame[1])

    # the damaged cells of an output frame (all of them if the input's frames are a different size), or None
    def damage(self, grey):
        if self.empty:
            return None
        self.__fill()
        if len(self.ahead[0]) != len(grey):
            return bytes([1]) * len(grey)
        best = min(range(len(self.ahead)), key=lambda k: sum(abs(x - y) for x, y in zip(self.ahead[k], grey)))
        del self.ahead[:best]  # keeps the match, so a repeated frame can match it again
        return bytes(abs(x - y) > THRESHOLD for x, y in zip(self.ahead[0], grey))

#
# A map of the output's bytes when there's no picture: (columns, brightness,
# damage) for up to columns x rows cells, each a chunk of the file, damaged if
# any of its bytes differ from the input's at the same position
#
def _byte_map(before, after, columns, rows):
    cells = min(columns * rows, len(after))
    edges = [len(after) * i // max(1, cells) for i in range(cells + 1)]
    damage = bytes(before[a:z] != after[a:z] for a, z in zip(edges, edges[1:]))
    return max(1, min(columns, cells)), bytes(200 if hit else 60 for hit in damage), damage
