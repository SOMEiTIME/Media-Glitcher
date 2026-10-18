#!/usr/bin/env python3

# Runs glitch operations on the raw data of a file.
#
# Line operations (swap, corrupt) split the data into lines first, the original
# way this tool worked. Byte operations work on the bytes directly, so their
# spacing and header are exact sizes. Both kinds can be mixed in one run and
# are applied in order.
#
# This module has no dependency on the CLI so other programs and tests can use it.

import io, itertools, random
import byte_ops
from media import media

DEFAULT_HEADER_LENGTH = 15   # lines line operations leave alone; 15 is good for video, 0 may suit images
DEFAULT_HEADER_BYTES = 1024  # bytes byte operations leave alone; keeps most file signatures and basic headers

# Each operation's parameters in command line order, as (name, type, smallest allowed value)
OPERATIONS = {
    "swap": (("interval", int, 0), ("flavour", int, None)),
    "corrupt": (("interval", int, 0), ("flavour", int, None)),
    "byte-swap": (("size", int, 1), ("every", int, 1)),
    "byte-corrupt": (("every", int, 1),),
    "bitflip": (("rate", float, 0),),
    "repeat": (("size", int, 1), ("every", int, 1)),
}
LINE_OPERATIONS = ("swap", "corrupt")

class GlitchError(ValueError):
    pass

def is_line_operation(op):
    return op["type"] in LINE_OPERATIONS

#
# Glitches data (bytes) with a list of operations, e.g.
# [{"type": "byte-swap", "size": 64, "every": 5000}], and returns the new bytes.
# The same seed and operations always give the same output
#
def glitch(data, operations, header_length=DEFAULT_HEADER_LENGTH, header_bytes=DEFAULT_HEADER_BYTES, seed=None):
    rng = random.Random(seed)
    data = bytes(data)
    # consecutive line operations share one split, the way they always ran
    for line_mode, group in itertools.groupby(operations, is_line_operation):
        if line_mode:
            data = _line_pass(data, list(group), header_length, rng)
        else:
            data = _byte_pass(data, list(group), header_bytes, rng)
    return data

def _line_pass(data, operations, header_length, rng):
    # latin-1 maps bytes 1:1 to characters, and newline="" splits on \n, \r and \r\n
    # exactly like reading the file in text mode did
    lines = io.StringIO(data.decode("latin-1"), newline="").readlines()
    if len(lines) < header_length:
        raise GlitchError("file has only %d lines, fewer than the header length (%d)" % (len(lines), header_length))
    lines_media = media(lines, header_length, rng)
    for op in operations:
        if op["type"] == "swap":
            lines_media.glitch_random_swap(op["interval"], op["flavour"])
        else:
            lines_media.glitch_corrupt(op["interval"], op["flavour"])
    return lines_media.text().encode("latin-1")

def _byte_pass(data, operations, header_bytes, rng):
    if len(data) <= header_bytes:
        raise GlitchError("file has only %d bytes, not more than the byte header (%d)" % (len(data), header_bytes))
    data = bytearray(data)
    for op in operations:
        function = getattr(byte_ops, op["type"].replace("-", "_"))
        function(data, header_bytes, rng, *(op[name] for name, _, _ in OPERATIONS[op["type"]]))
    return bytes(data)
