#!/usr/bin/env python3

# Targets for uncompressed formats: each finds the raw pixel or sample data, so
# byte operations leave the real header (and anything stored after the data,
# like colour profiles or metadata chunks) alone. Any byte value is valid raw
# data, so unlike JPEG no repair step is needed.

# AIFF-C compression codes that are plain samples (macOS writes "twos" for big-endian 16-bit)
AIFC_UNCOMPRESSED = {b"NONE", b"twos", b"sowt", b"raw ", b"in24", b"in32", b"23ni", b"42ni",
                     b"fl32", b"FL32", b"fl64", b"FL64"}

class FormatError(ValueError):
    pass

#
# bmp-pixels target: the pixel array of an uncompressed BMP
#
def bmp_pixels(data):
    if data[:2] != b"BM" or len(data) < 34:
        raise FormatError("not a BMP (it doesn't start with BM)")
    if int.from_bytes(data[14:18], "little") < 40:
        raise FormatError("old OS/2 BMPs aren't supported")
    offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = int.from_bytes(data[22:26], "little", signed=True)  # negative means stored top-down
    bits = int.from_bytes(data[28:30], "little")
    compression = int.from_bytes(data[30:34], "little")
    if compression not in (0, 3, 6):  # plain, or plain with bit masks
        raise FormatError("compressed BMPs aren't supported")
    row = (bits * width + 31) // 32 * 4  # rows are padded to 4 bytes
    return _checked(data, offset, offset + row * abs(height))

#
# ppm-pixels target: the pixel data of a binary PPM (P6), PGM (P5) or PBM (P4).
# The header is the magic number, width, height and (except for PBM) the
# maximum value, separated by whitespace and # comments
#
def ppm_pixels(data):
    kind = data[:2]
    if kind not in (b"P4", b"P5", b"P6"):
        raise FormatError("not a binary PPM, PGM or PBM (it doesn't start with P4, P5 or P6)")
    fields, pos = [], 2
    while len(fields) < (2 if kind == b"P4" else 3):
        while pos < len(data) and (data[pos:pos + 1].isspace() or data[pos] == ord("#")):
            if data[pos] == ord("#"):
                pos = data.find(b"\n", pos)
                if pos == -1:
                    raise FormatError("header ends in a comment")
            pos += 1
        start = pos
        while pos < len(data) and data[pos:pos + 1].isdigit():
            pos += 1
        if start == pos:
            raise FormatError("header has a missing or invalid number at byte %d" % start)
        fields.append(int(data[start:pos]))
    pos += 1  # exactly one whitespace byte before the data
    width, height = fields[:2]
    if kind == b"P4":
        size = (width + 7) // 8 * height
    else:
        channels = 3 if kind == b"P6" else 1
        size = width * height * channels * (2 if fields[2] > 255 else 1)
    return _checked(data, pos, pos + size)

#
# wav-samples target: the data chunk of an uncompressed (PCM or float) WAV
#
def wav_samples(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise FormatError("not a WAV (it doesn't start with RIFF....WAVE)")
    chunks = _chunks(data, 12, "little")
    if "fmt " not in chunks or "data" not in chunks:
        raise FormatError("WAV has no fmt or data chunk")
    fmt = chunks["fmt "][0]
    if int.from_bytes(data[fmt:fmt + 2], "little") not in (1, 3, 0xFFFE):  # PCM, float, extensible
        raise FormatError("compressed WAVs aren't supported")
    return [chunks["data"]]

#
# aiff-samples target: the sample data in the SSND chunk of an AIFF, or of an
# AIFF-C that isn't compressed
#
def aiff_samples(data):
    if data[:4] != b"FORM" or data[8:12] not in (b"AIFF", b"AIFC"):
        raise FormatError("not an AIFF (it doesn't start with FORM....AIFF)")
    chunks = _chunks(data, 12, "big")
    if "COMM" not in chunks or "SSND" not in chunks:
        raise FormatError("AIFF has no COMM or SSND chunk")
    comm = chunks["COMM"][0]
    if data[8:12] == b"AIFC" and data[comm + 18:comm + 22] not in AIFC_UNCOMPRESSED:
        raise FormatError("compressed AIFF-C files aren't supported")
    start, end = chunks["SSND"]
    offset = int.from_bytes(data[start:start + 4], "big")  # padding before the first sample
    return _checked(data, start + 8 + offset, end)

# {chunk id: (content start, content end)} for a RIFF/IFF file, first of each id
def _chunks(data, pos, byteorder):
    found = {}
    while pos + 8 <= len(data):
        name = data[pos:pos + 4].decode("latin-1")
        size = int.from_bytes(data[pos + 4:pos + 8], byteorder)
        found.setdefault(name, (pos + 8, min(pos + 8 + size, len(data))))
        pos += 8 + size + size % 2  # chunks are padded to an even length
    return found

# the range as a one-item list, if it's inside the file and not empty
def _checked(data, start, end):
    if not 0 < start < end <= len(data):
        raise FormatError("header says the data is at bytes %d-%d, but the file has %d bytes" % (start, end, len(data)))
    return [(start, end)]
