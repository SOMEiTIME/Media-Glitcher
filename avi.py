#!/usr/bin/env python3

# AVI support for datamoshing: MPEG-4 part 2 video (Xvid, DivX, ffmpeg's mpeg4)
# in an AVI. Each video frame is a chunk in the "movi" list, so frames can be
# dropped or repeated without decoding anything.
#
# A keyframe (I-frame) holds a whole picture; the frames after it (P-frames)
# only hold motion vectors and changes against the previous frame. Dropping a
# keyframe makes the next P-frames move the old picture around instead of
# starting fresh, which is the datamosh look. Repeating a P-frame repeats its
# motion, so the picture smears and blooms.
#
# The index (idx1) is dropped when the file is rebuilt, since players rebuild
# it by scanning, and a stale one points at the wrong frames.

class AviError(ValueError):
    pass

# MPEG-4 part 2 video object plane header: start code, then 2 bits of coding type (0 = I, 1 = P, 2 = B)
VOP_START = b"\x00\x00\x01\xb6"

def _le(data, pos):
    return int.from_bytes(data[pos:pos + 4], "little")

# True for a video frame chunk id, e.g. b"00dc" (compressed) or b"00db" (uncompressed)
def _is_video(chunk_id):
    return chunk_id[:2].isdigit() and chunk_id[2:] in (b"dc", b"db")

def is_keyframe(payload):
    at = payload.find(VOP_START, 0, 64)
    return at != -1 and at + 4 < len(payload) and payload[at + 4] >> 6 == 0

# the (id, start, end) of each chunk of a RIFF list's contents
def _chunks(data, pos, end):
    found = []
    while pos + 8 <= end:
        size = _le(data, pos + 4)
        if pos + 8 + size > len(data):
            raise AviError("chunk at byte %d runs past the end of the file" % pos)
        found.append((data[pos:pos + 4], pos, pos + 8 + size))
        pos += 8 + size + size % 2  # chunks are padded to an even length
    return found

# where the movi list starts, its chunks, and the top level chunks after it that should be kept
def _layout(data):
    if data[:4] != b"RIFF" or data[8:12] != b"AVI ":
        raise AviError("not an AVI (it doesn't start with RIFF....AVI )")
    top = _chunks(data, 12, len(data))
    movi = [c for c in top if c[0] == b"LIST" and data[c[1] + 8:c[1] + 12] == b"movi"]
    if len(movi) != 1:
        raise AviError("expected one movi list, found %d (files over 1 GB aren't supported)" % len(movi))
    _, movi_start, movi_end = movi[0]
    frames = _chunks(data, movi_start + 12, movi_end)
    if any(chunk_id == b"LIST" for chunk_id, _, _ in frames):
        raise AviError("AVIs with 'rec' lists aren't supported")
    if not any(is_keyframe(data[s + 8:e]) for i, s, e in frames if _is_video(i)):
        raise AviError("no MPEG-4 part 2 video found (convert it with ffmpeg -c:v mpeg4, or libxvid)")
    after = [c for c in top if c[1] > movi_start and c[0] != b"idx1"]
    return movi_start, frames, after

#
# avi-frames target: the compressed data of each video frame. Chunk headers,
# audio and the file's structure stay untouched, so byte operations damage the
# picture without breaking the container
#
def frame_ranges(data):
    _, frames, _ = _layout(data)
    return [(s + 8, e) for i, s, e in frames if _is_video(i) and e > s + 8]

#
# Splits an AVI into (before, frames, after) where before and after are the
# bytes around the movi list (after has no index) and frames is a list of
# [chunk id, payload]. Audio and other chunks stay in the list between frames
#
def split(data):
    movi_start, frames, after = _layout(data)
    before = data[12:movi_start]
    return before, [[i, data[s + 8:e]] for i, s, e in frames], b"".join(data[s:e + (e - s) % 2] for _, s, e in after)

# puts an AVI back together from the parts split() returned, with sizes fixed up
def join(before, frames, after):
    movi = b"movi" + b"".join(i + len(p).to_bytes(4, "little") + p + b"\x00" * (len(p) % 2) for i, p in frames)
    body = b"AVI " + before + b"LIST" + len(movi).to_bytes(4, "little") + movi + after
    return b"RIFF" + len(body).to_bytes(4, "little") + body

# True for frames that are video; the others are audio and padding
def _video(frame):
    return _is_video(frame[0])

#
# iframe-drop: keeps the first `keep` keyframes and removes every one after
# them, so the video carries on moving the last picture it had
#
def iframe_drop(frames, rng, keep):
    seen, kept = 0, []
    for frame in frames:
        if _video(frame) and is_keyframe(frame[1]):
            seen += 1
            if seen > keep:
                continue
        kept.append(frame)
    frames[:] = kept

#
# pframe-repeat: once every `every` video frames, picks a P-frame in that
# stretch and plays it `count` more times in a row
#
def pframe_repeat(frames, rng, every, count):
    video = [n for n, frame in enumerate(frames) if _video(frame)]
    picks = []
    for window in range(0, len(video), every):
        pframes = [n for n in video[window:window + every] if frames[n][1] and not is_keyframe(frames[n][1])]
        if pframes:
            picks.append(rng.choice(pframes))
    for n in reversed(picks):
        frames[n + 1:n + 1] = [list(frames[n]) for _ in range(count)]
