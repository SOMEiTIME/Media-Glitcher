#!/usr/bin/env python3

# JPEG structure for the format-aware targets. Reads only the marker layout
# (segment lengths and where the compressed image data sits); it never decodes
# the image.
#
# A JPEG is a list of segments, each starting with an FF xx marker. Inside the
# compressed data after a start-of-scan (SOS) marker, an FF byte is always
# followed by 00 (an escaped FF) or D0-D7 (a restart marker); anything else
# ends the data. So targets must never leave a stray FF behind.

SOS, DQT, EOI = 0xDA, 0xDB, 0xD9
RESTARTS = range(0xD0, 0xD8)
NO_LENGTH = {0x01, 0xD8, *RESTARTS}  # markers without a length field
SCAN = "scan"                        # pseudo segment: the compressed data after an SOS

class JpegError(ValueError):
    pass

# whether an FF followed by this byte, inside compressed data, ends the data
def _ends_data(next_byte):
    return next_byte != 0 and next_byte not in RESTARTS

#
# Returns the segments of the main image as (marker, start, end), where
# start:end is the segment's content after its length field. Each SOS is
# followed by a (SCAN, start, end) entry for its compressed data. Parsing stops
# at the end-of-image marker; anything after it (iPhones append extra images
# there) is not part of the result, so targets leave it alone
#
def segments(data):
    if data[:2] != b"\xff\xd8":
        raise JpegError("not a JPEG (it doesn't start with FF D8)")
    found = []
    pos = 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise JpegError("expected a marker at byte %d" % pos)
        while pos < len(data) and data[pos] == 0xFF:  # extra FF bytes before a marker are padding
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker == EOI:
            break
        if marker in NO_LENGTH:
            continue
        length = int.from_bytes(data[pos:pos + 2], "big")
        if length < 2 or pos + length > len(data):
            raise JpegError("segment at byte %d runs past the end of the file" % pos)
        found.append((marker, pos + 2, pos + length))
        pos += length
        if marker == SOS:
            end = _scan_end(data, pos)
            found.append((SCAN, pos, end))
            pos = end
    return found

# where compressed data starting at pos ends: the first FF that isn't escaped or a restart
def _scan_end(data, pos):
    while True:
        pos = data.find(b"\xff", pos)
        if pos == -1 or pos + 1 >= len(data):
            return len(data)  # truncated file: the data runs to the end
        if _ends_data(data[pos + 1]):
            return pos
        pos += 2

#
# jpeg-scan target: the compressed image data. Huffman and quantization tables,
# headers and metadata stay untouched
#
def scan_ranges(data):
    return [(start, end) for marker, start, end in segments(data) if marker == SCAN]

#
# After glitching, turns every FF that no longer starts an escaped FF or a
# restart marker into FE, so the compressed data still runs to its real end
#
def repair_scan(data, ranges):
    for start, end in ranges:
        pos = data.find(b"\xff", start, end)
        while pos != -1:
            if pos + 1 >= end or _ends_data(data[pos + 1]):
                data[pos] = 0xFE
            pos = data.find(b"\xff", pos + 1, end)

#
# jpeg-tables target: the values of the quantization tables, which control how
# coarsely each frequency is stored. Each table's precision/id byte is skipped
#
def table_ranges(data):
    ranges = []
    for marker, start, end in segments(data):
        if marker != DQT:
            continue
        pos = start
        while pos < end:
            size = 128 if data[pos] >> 4 else 64  # 16-bit or 8-bit values
            ranges.append((pos + 1, min(pos + 1 + size, end)))
            pos += 1 + size
    return ranges

#
# Quantization values of zero aren't allowed (decoders reject them), so any
# zero the operations created becomes 1. The byte before each range is its
# table's precision/id byte, which says whether values are 8 or 16 bits
#
def repair_tables(data, ranges):
    for start, end in ranges:
        width = 2 if data[start - 1] >> 4 else 1
        for pos in range(start, end - width + 1, width):
            if not any(data[pos:pos + width]):
                data[pos + width - 1] = 1
