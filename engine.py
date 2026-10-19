#!/usr/bin/env python3

# Runs glitch operations on the raw data of a file.
#
# Line operations (swap, corrupt) split the data into lines first, the original
# way this tool worked. Byte operations work on the bytes directly, so their
# spacing and header are exact sizes. Frame operations (iframe-drop,
# pframe-repeat) datamosh an AVI by removing or repeating whole video frames.
# All kinds can be mixed in one run and are applied in order.
#
# A target limits byte operations to the parts of a format that are safe to
# damage, e.g. only a JPEG's compressed image data.
#
# This module has no dependency on the CLI so other programs and tests can use it.

import io, itertools, random
import avi, byte_ops, jpeg, uncompressed
from media import media

DEFAULT_HEADER_LENGTH = 15   # protected lines in line mode; 15 is good for video, 0 may suit images
DEFAULT_HEADER_BYTES = 1024  # protected bytes in byte mode; keeps most file signatures and basic headers

# Each operation's parameters in command line order, as (name, type, smallest allowed value)
OPERATIONS = {
    "swap": (("interval", int, 0), ("flavour", int, None)),
    "corrupt": (("interval", int, 0), ("flavour", int, None)),
    "byte-swap": (("size", int, 1), ("every", int, 1)),
    "byte-corrupt": (("every", int, 1),),
    "bitflip": (("rate", float, 0),),
    "repeat": (("size", int, 1), ("every", int, 1)),
    "iframe-drop": (("keep", int, 1),),
    "pframe-repeat": (("every", int, 1), ("count", int, 1)),
}
LINE_FUNCTIONS = {"swap": media.glitch_random_swap, "corrupt": media.glitch_corrupt}
BYTE_FUNCTIONS = {"byte-swap": byte_ops.byte_swap, "byte-corrupt": byte_ops.byte_corrupt,
                  "bitflip": byte_ops.bitflip, "repeat": byte_ops.repeat}
FRAME_FUNCTIONS = {"iframe-drop": avi.iframe_drop, "pframe-repeat": avi.pframe_repeat}

# Format targets, as (find the ranges to glitch, repair the file afterwards).
# The "all" target is simply everything after header_bytes
FORMAT_TARGETS = {
    "jpeg-scan": (jpeg.scan_ranges, jpeg.repair_scan),
    "jpeg-tables": (jpeg.table_ranges, jpeg.repair_tables),
    "bmp-pixels": (uncompressed.bmp_pixels, None),
    "ppm-pixels": (uncompressed.ppm_pixels, None),
    "wav-samples": (uncompressed.wav_samples, None),
    "aiff-samples": (uncompressed.aiff_samples, None),
    "avi-frames": (avi.frame_ranges, None),
}
TARGETS = ("all", "auto", *FORMAT_TARGETS)
DEFAULT_TARGET = "all"

class GlitchError(ValueError):
    pass

def is_line_operation(op):
    return op["type"] in LINE_FUNCTIONS

def is_frame_operation(op):
    return op["type"] in FRAME_FUNCTIONS

def is_byte_operation(op):
    return op["type"] in BYTE_FUNCTIONS

# an operation's parameter values, in OPERATIONS order
def _values(op):
    return [op[name] for name, _, _ in OPERATIONS[op["type"]]]

#
# Glitches data (bytes) with a list of operations, e.g.
# [{"type": "byte-swap", "size": 64, "every": 5000}], and returns the new bytes.
# The same seed and operations always give the same output
#
def glitch(data, operations, header_length=DEFAULT_HEADER_LENGTH, header_bytes=DEFAULT_HEADER_BYTES, seed=None,
           target=DEFAULT_TARGET):
    rng = random.Random(seed)
    data = bytes(data)
    # consecutive operations of one kind share one pass (for line operations, one split, the way they always ran)
    for kind, group in itertools.groupby(operations, _kind):
        if kind == "line":
            data = _line_pass(data, list(group), header_length, rng)
        elif kind == "frame":
            data = _frame_pass(data, list(group), rng)
        else:
            ranges, repair = _target(data, target, header_bytes)
            data = _byte_pass(data, list(group), ranges, repair, rng)
    return data

def _kind(op):
    return "line" if is_line_operation(op) else "frame" if is_frame_operation(op) else "byte"

def _line_pass(data, operations, header_length, rng):
    # latin-1 maps bytes 1:1 to characters, and newline="" splits on \n, \r and \r\n
    # exactly like reading the file in text mode did
    lines = io.StringIO(data.decode("latin-1"), newline="").readlines()
    if len(lines) < header_length:
        raise GlitchError("file has only %d lines, fewer than the header length (%d)" % (len(lines), header_length))
    lines_media = media(lines, header_length, rng)
    for op in operations:
        LINE_FUNCTIONS[op["type"]](lines_media, *_values(op))
    return lines_media.text().encode("latin-1")

def _frame_pass(data, operations, rng):
    try:
        before, frames, after = avi.split(data)
    except avi.AviError as error:
        raise GlitchError("can't use %s: %s" % (operations[0]["type"], error))
    for op in operations:
        FRAME_FUNCTIONS[op["type"]](frames, rng, *_values(op))
    return avi.join(before, frames, after)

# the format target "auto" picks from the file's first bytes; "all" if it's none of them
def detect_target(data):
    if data[:2] == b"\xff\xd8":
        return "jpeg-scan"
    if data[:2] == b"BM":
        return "bmp-pixels"
    if data[:2] in (b"P4", b"P5", b"P6"):
        return "ppm-pixels"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav-samples"
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return "avi-frames"
    if data[:4] == b"FORM" and data[8:12] in (b"AIFF", b"AIFC"):
        return "aiff-samples"
    return "all"

# the (start, end) ranges byte operations may change, and the repair step to run after
def _target(data, target, header_bytes):
    if target == "auto":
        target = detect_target(data)
    if target == "all":
        if len(data) <= header_bytes:
            raise GlitchError("file has only %d bytes, not more than the byte header (%d)" % (len(data), header_bytes))
        return [(header_bytes, len(data))], None
    find, repair = FORMAT_TARGETS[target]
    try:
        ranges = find(data)
    except (jpeg.JpegError, uncompressed.FormatError, avi.AviError) as error:
        raise GlitchError("can't use target %s: %s" % (target, error))
    if not ranges:
        raise GlitchError("can't use target %s: nothing to glitch in this file" % target)
    return ranges, repair

# runs byte operations on the target ranges joined together, then puts them back
def _byte_pass(data, operations, ranges, repair, rng):
    part = bytearray(b"".join(data[start:end] for start, end in ranges))
    for op in operations:
        BYTE_FUNCTIONS[op["type"]](part, 0, rng, *_values(op))
    data = bytearray(data)
    pos = 0
    for start, end in ranges:
        data[start:end] = part[pos:pos + end - start]
        pos += end - start
    if repair:
        repair(data, ranges)
    return bytes(data)
