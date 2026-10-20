#!/usr/bin/env python3

# Pixel sorting: within each row (or line at an angle), runs of pixels whose
# sort key is inside a threshold are sorted by that key, giving streaks.
#
# Unlike the other modes this works on decoded pixels. Binary PPM (P6, 8-bit)
# is read and written directly; JPEG, PNG and BMP go through ffmpeg, and the
# output is the same format as the input.
#
# NumPy is only imported when pixels are sorted, so the rest of the tool stays
# stdlib only.

import math, subprocess
import uncompressed

KEYS = ("brightness", "hue", "saturation", "r", "g", "b")

# ffmpeg encoder (and options) for each format, by its first bytes
FFMPEG_FORMATS = (
    (b"\xff\xd8", ["-c:v", "mjpeg", "-q:v", "2"]),
    (b"\x89PNG", ["-c:v", "png"]),
    (b"BM", ["-c:v", "bmp"]),
)

class PixelError(ValueError):
    pass

def _numpy():
    try:
        import numpy
    except ImportError:
        raise PixelError("pixel sorting needs NumPy (pip install numpy)")
    return numpy

#
# The sort key of every pixel of an H x W x 3 uint8 frame, from 0 to 1
#
def sort_key(frame, key):
    np = _numpy()
    rgb = frame.astype(np.float64) / 255
    if key in ("r", "g", "b"):
        return rgb[..., "rgb".index(key)]
    if key == "brightness":
        return rgb @ np.array([0.299, 0.587, 0.114])  # Rec. 601 luma
    high, low = rgb.max(axis=2), rgb.min(axis=2)
    spread = high - low
    if key == "saturation":
        return np.where(high > 0, spread / np.where(high > 0, high, 1), 0)
    # hue as in HSV; grey pixels get 0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    safe = np.where(spread > 0, spread, 1)
    hue = np.where(high == r, (g - b) / safe % 6, np.where(high == g, (b - r) / safe + 2, (r - g) / safe + 4))
    return np.where(spread > 0, hue / 6, 0)

#
# Sorts the pixels of an H x W x 3 uint8 frame and returns a new frame of the
# same shape. Pixels whose key is from low to high (0 to 1) can move; each
# unbroken run of them along a line is sorted by key, lowest first. The lines
# run at angle degrees: 0 left to right, 90 top to bottom, 180 right to left.
# No randomness, so the same frame and settings always give the same output
#
def pixel_sort(frame, key, low, high, angle=0):
    np = _numpy()
    height, width = frame.shape[:2]
    values = sort_key(frame, key).ravel()
    mask = (values >= low) & (values <= high)

    # walk the pixels line by line: each pixel's line and position along it at this angle
    radians = math.radians(angle % 360)
    cos, sin = round(math.cos(radians), 12), round(math.sin(radians), 12)  # exact at multiples of 90
    y, x = np.indices((height, width)).reshape(2, -1)
    along = x * cos + y * sin
    line = np.rint(y * cos - x * sin)
    order = np.lexsort((along, line))

    # a run starts at each masked pixel after an unmasked one or a new line; every unmasked
    # pixel is a group of its own, so sorting by (group, key) only moves pixels within runs
    mask, line = mask[order], line[order]
    new_line = np.ones(len(order), bool)
    new_line[1:] = line[1:] != line[:-1]
    run_start = mask & (new_line | np.concatenate(([True], ~mask[:-1])))
    group = np.cumsum(run_start | ~mask)
    sorted_order = order[np.lexsort((values[order], group))]

    pixels = frame.reshape(-1, 3)
    out = pixels.copy()
    out[order] = pixels[sorted_order]
    return out.reshape(frame.shape)

#
# Decodes an image file's bytes into an H x W x 3 uint8 frame. Returns the
# frame and a function that encodes a frame back into the same format
#
def decode(data):
    np = _numpy()
    try:
        kind, fields, _ = uncompressed.ppm_header(data)
        native = kind == b"P6" and fields[2] == 255
    except uncompressed.FormatError:
        native = False
    encode = _ppm  # also for PGM, PBM and 16-bit PPM, which come back as 8-bit PPM
    if not native:
        if not data.startswith((b"P4", b"P5", b"P6")):
            encoder = _ffmpeg_encoder(data)
            encode = lambda frame: _ffmpeg(_ppm(frame), ["-f", "image2pipe", *encoder], ["-f", "ppm_pipe"])
        data = _ffmpeg(data, ["-f", "image2pipe", "-c:v", "ppm", "-pix_fmt", "rgb24"])
    kind, fields, pos = uncompressed.ppm_header(data)
    width, height = fields[:2]
    if len(data) < pos + width * height * 3:
        raise PixelError("PPM is shorter than its width and height say")
    return np.frombuffer(data, np.uint8, width * height * 3, pos).reshape(height, width, 3), encode

def _ppm(frame):
    height, width = frame.shape[:2]
    return b"P6\n%d %d\n255\n" % (width, height) + frame.tobytes()

def _ffmpeg_encoder(data):
    for magic, encoder in FFMPEG_FORMATS:
        if data.startswith(magic):
            return encoder
    raise PixelError("pixel sorting works on JPEG, PNG, BMP and PPM images")

# runs ffmpeg with data on stdin and returns its stdout
def _ffmpeg(data, output_args, input_args=()):
    command = ["ffmpeg", "-v", "error", *input_args, "-i", "pipe:0", *output_args, "pipe:1"]
    try:
        result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise PixelError("pixel sorting this format needs ffmpeg: %s" % error)
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise PixelError("ffmpeg failed: %s" % (lines[-1] if lines else "exit code %d" % result.returncode))
    return result.stdout
