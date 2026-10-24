#!/usr/bin/env python3

# Pixel sorting: within each row (or line at an angle), runs of pixels whose
# sort key is inside a threshold are sorted by that key, giving streaks.
#
# Unlike the other modes this works on decoded pixels. Binary PPM (P6, 8 or
# 16 bits per channel) is read and written directly, keeping its depth; JPEG,
# PNG and BMP go through ffmpeg, and the output is the same format as the input.
# Video (MP4, MOV, AVI) is streamed through ffmpeg a frame at a time.
#
# NumPy is only imported when pixels are sorted, so the rest of the tool stays
# stdlib only.

import math, os, subprocess, tempfile
import uncompressed

KEYS = ("brightness", "hue", "saturation", "r", "g", "b")

# ffmpeg encoder (and options) for each format, by its first bytes
FFMPEG_FORMATS = (
    (b"\xff\xd8", ["-c:v", "mjpeg", "-q:v", "2"]),
    (b"\x89PNG", ["-c:v", "png"]),
    (b"BM", ["-c:v", "bmp"]),
)

# ffmpeg output options for video. MP4 and MOV come back as H.264 MP4; AVI stays
# MPEG-4 Part 2, so frame operations (iframe-drop, pframe-repeat) still work on it
MP4_OUTPUT = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-f", "mp4"]
AVI_OUTPUT = ["-c:v", "mpeg4", "-q:v", "2", "-bf", "0", "-f", "avi"]

# brands of ftyp files that are images (HEIC, AVIF), not video
IMAGE_BRANDS = (b"heic", b"heix", b"mif1", b"msf1", b"avif")

class PixelError(ValueError):
    pass

def _numpy():
    try:
        import numpy
    except ImportError:
        raise PixelError("pixel sorting needs NumPy (pip install numpy)")
    return numpy

#
# The sort key of every pixel of an H x W x 3 frame of unsigned ints
# (uint8 or uint16, using the full range), from 0 to 1
#
def sort_key(frame, key):
    np = _numpy()
    rgb = frame.astype(np.float64) / np.iinfo(frame.dtype).max
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
# Sorts the pixels of an H x W x 3 frame (as for sort_key) and returns a new
# frame of the same shape and dtype. Pixels whose key is from low to high (0
# to 1) can move; each unbroken run of them along a line is sorted by key,
# lowest first. The lines run at angle degrees: 0 left to right, 90 top to
# bottom, 180 right to left. No randomness, so the same frame and settings
# always give the same output
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
# Decodes a file's bytes into H x W x 3 frames (uint8, or big-endian uint16 for
# 16-bit PPM). Returns the frames (an iterable: one for an image, streamed for
# video) and a function that encodes an iterable of frames back into the same
# format
#
def decode(data):
    output = _video_output(data)
    if output:
        return _video(data, output)
    frame, encode = _image(data)
    return [frame], lambda frames: encode(*frames)

def _image(data):
    np = _numpy()
    try:
        kind, fields, _ = uncompressed.ppm_header(data)
        native = kind == b"P6" and fields[2] in (255, 65535)
    except uncompressed.FormatError:
        native = False
    encode = _ppm  # also for PGM, PBM and other PPM depths, which come back as 8-bit PPM
    if not native:
        if not data.startswith((b"P4", b"P5", b"P6")):
            encoder = _ffmpeg_encoder(data)
            encode = lambda frame: _ffmpeg(_ppm(frame), ["-f", "image2pipe", *encoder], ["-f", "ppm_pipe"])
        data = _ffmpeg(data, ["-f", "image2pipe", "-c:v", "ppm", "-pix_fmt", "rgb24"])
    kind, fields, pos = uncompressed.ppm_header(data)
    width, height, maxval = fields
    dtype = np.dtype(np.uint8 if maxval == 255 else ">u2")  # PPM samples are big-endian
    count = width * height * 3
    if len(data) < pos + count * dtype.itemsize:
        raise PixelError("PPM is shorter than its width and height say")
    return np.frombuffer(data, dtype, count, pos).reshape(height, width, 3), encode

def _ppm(frame):
    height, width = frame.shape[:2]
    return b"P6\n%d %d\n%d\n" % (width, height, _numpy().iinfo(frame.dtype).max) + frame.tobytes()

def _ffmpeg_encoder(data):
    for magic, encoder in FFMPEG_FORMATS:
        if data.startswith(magic):
            return encoder
    raise PixelError("pixel sorting works on JPEG, PNG, BMP and PPM images, and MP4, MOV and AVI video")

def _video_output(data):
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return AVI_OUTPUT
    if data[4:8] == b"ftyp" and data[8:12] not in IMAGE_BRANDS:
        return MP4_OUTPUT
    return None

#
# Streams a video's frames out of one ffmpeg and into another, so only one
# frame is in memory at a time. ffmpeg needs a seekable file for MP4 and MOV,
# so the input and output go through a temporary directory. Rotation (as set by
# phones) is applied while decoding, and the audio is copied
#
def _video(data, output):
    np = _numpy()
    folder = tempfile.TemporaryDirectory()
    source, result = os.path.join(folder.name, "in"), os.path.join(folder.name, "out")
    with open(source, "wb") as f:
        f.write(data)

    def frames():
        decoder = _start(["-i", source, "-map", "0:v:0", "-f", "image2pipe", "-c:v", "ppm", "-pix_fmt", "rgb24",
                          "pipe:1"], folder.name, stdout=subprocess.PIPE)
        try:
            # ffmpeg writes each frame as "P6\nW H\n255\n" and the pixels
            while True:
                header = [decoder.stdout.readline() for _ in range(3)]
                if not header[0]:
                    break
                width, height = map(int, header[1].split())
                pixels = decoder.stdout.read(width * height * 3)
                if len(pixels) < width * height * 3:
                    break  # cut off; _finish says why
                yield np.frombuffer(pixels, np.uint8).reshape(height, width, 3)
            _finish(decoder)
        finally:
            _stop(decoder)

    def encode(frames):
        encoder = None
        try:
            encoder = _start(["-f", "ppm_pipe", "-framerate", _frame_rate(source), "-i", "pipe:0", "-i", source,
                              "-map", "0:v", "-map", "1:a?", "-c:a", "copy", *output, "-y", result],
                             folder.name, stdin=subprocess.PIPE)
            try:
                for frame in frames:
                    encoder.stdin.write(_ppm(frame))
                encoder.stdin.close()
            except BrokenPipeError:
                pass  # the encoder stopped; _finish says why
            _finish(encoder)
            with open(result, "rb") as f:
                return f.read()
        finally:
            decoded.close()  # stops the decoder if it's still running
            if encoder:
                _stop(encoder)
            folder.cleanup()

    decoded = frames()
    return decoded, encode

# the video's frame rate as ffprobe gives it, e.g. "30/1"; the average if known, as phones vary it
def _frame_rate(source):
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate,r_frame_rate",
               "-of", "default=noprint_wrappers=1", source]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise PixelError("pixel sorting video needs ffprobe (part of ffmpeg): %s" % error)
    if result.returncode != 0:
        raise _failed("ffprobe", result.stderr, result.returncode)
    fields = dict(line.split("=", 1) for line in result.stdout.decode("ascii", "replace").split() if "=" in line)
    for name in ("avg_frame_rate", "r_frame_rate"):
        if fields.get(name, "0/0") != "0/0":
            return fields[name]
    raise PixelError("ffprobe found no video stream")

# starts ffmpeg with its messages going to a log file in folder, so a full pipe can't stall it
def _start(args, folder, **pipes):
    log = tempfile.TemporaryFile(dir=folder)
    try:
        process = subprocess.Popen(["ffmpeg", "-v", "error", *args], stderr=log, **pipes)
    except OSError as error:
        log.close()
        raise PixelError("pixel sorting this format needs ffmpeg: %s" % error)
    process.log = log
    return process

# waits for ffmpeg to exit and raises its last message if it failed
def _finish(process):
    if process.wait() != 0:
        process.log.seek(0)
        raise _failed("ffmpeg", process.log.read(), process.returncode)

# kills ffmpeg if it's still running and closes its pipes and log
def _stop(process):
    if process.poll() is None:
        process.kill()
    process.wait()
    for f in (process.stdin, process.stdout, process.log):
        if f:
            f.close()

# runs ffmpeg with data on stdin and returns its stdout
def _ffmpeg(data, output_args, input_args=()):
    command = ["ffmpeg", "-v", "error", *input_args, "-i", "pipe:0", *output_args, "pipe:1"]
    try:
        result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise PixelError("pixel sorting this format needs ffmpeg: %s" % error)
    if result.returncode != 0:
        raise _failed("ffmpeg", result.stderr, result.returncode)
    return result.stdout

def _failed(tool, stderr, returncode):
    lines = stderr.decode("utf-8", "replace").strip().splitlines()
    return PixelError("%s failed: %s" % (tool, lines[-1] if lines else "exit code %d" % returncode))
