import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import engine, uncompressed

OPS = [{"type": "byte-swap", "size": 24, "every": 300}, {"type": "byte-corrupt", "every": 50},
       {"type": "bitflip", "rate": 0.01}, {"type": "repeat", "size": 48, "every": 600}]

def le(value, size):
    return value.to_bytes(size, "little")

# a BMP with a palette and padded rows, and `extra` bytes after the pixels (like a colour profile)
def bmp(width=13, height=-7, bits=8, compression=0, extra=b"ICC!"):
    palette = bytes(range(256)) * 4 if bits == 8 else b""
    offset = 54 + len(palette)
    row = (bits * width + 31) // 32 * 4
    pixels = bytes(i % 251 for i in range(row * abs(height)))
    info = le(40, 4) + le(width, 4) + height.to_bytes(4, "little", signed=True) \
        + le(1, 2) + le(bits, 2) + le(compression, 4) + bytes(20)
    data = b"BM" + le(offset + len(pixels) + len(extra), 4) + bytes(4) + le(offset, 4) + info + palette
    return data + pixels + extra, (offset, offset + len(pixels))

def chunk(name, content, byteorder="little"):
    return name + len(content).to_bytes(4, byteorder) + content + b"\x00" * (len(content) % 2)

def wav(format_tag=1, before=b"", after=b""):
    fmt = chunk(b"fmt ", le(format_tag, 2) + le(1, 2) + le(8000, 4) + le(16000, 4) + le(2, 2) + le(16, 2))
    samples = bytes(i % 256 for i in range(800))
    body = b"WAVE" + fmt + before + chunk(b"data", samples) + after
    start = 12 + len(fmt) + len(before) + 8
    return chunk(b"RIFF", body), (start, start + len(samples))

def aiff(kind=b"AIFF", compression=b"NONE", offset=6):
    comm = (1).to_bytes(2, "big") + bytes(4) + (16).to_bytes(2, "big") + bytes(10)  # channels, frames, bits, rate
    if kind == b"AIFC":
        comm += compression + b"\x00"
    samples = bytes(i % 256 for i in range(900))
    ssnd = chunk(b"SSND", offset.to_bytes(4, "big") + bytes(4) + bytes(offset) + samples, "big")
    body = kind + chunk(b"COMM", comm, "big") + ssnd
    start = 12 + 8 + len(comm) + len(comm) % 2 + 8 + 8 + offset
    return chunk(b"FORM", body, "big"), (start, start + len(samples))

class FormatTest(unittest.TestCase):
    def test_bmp(self):
        for bits in (1, 8, 24, 32):
            data, expected = bmp(bits=bits)
            self.assertEqual(uncompressed.bmp_pixels(data), [expected])
        for bad in (bmp(compression=1)[0], b"BM" + bytes(12) + le(12, 4) + bytes(30)):  # RLE, OS/2 header
            with self.assertRaises(uncompressed.FormatError):
                uncompressed.bmp_pixels(bad)

    def test_ppm(self):
        data = b"P6 # a comment\n3 2\n# another\n255\n" + bytes(18)
        self.assertEqual(uncompressed.ppm_pixels(data), [(len(data) - 18, len(data))])
        data = b"P5\n2 2\n65535\n" + bytes(8)  # 16-bit grey
        self.assertEqual(uncompressed.ppm_pixels(data), [(len(data) - 8, len(data))])
        data = b"P4\n10 2\n" + bytes(4)  # 1-bit rows padded to whole bytes
        self.assertEqual(uncompressed.ppm_pixels(data), [(len(data) - 4, len(data))])
        for bad in (b"P3\n1 1\n255\n0 0 0", b"P6\n3 x\n255\n", b"P6\n30 20\n255\n" + bytes(10)):
            with self.assertRaises(uncompressed.FormatError):
                uncompressed.ppm_pixels(bad)

    def test_wav(self):
        data, expected = wav(before=chunk(b"LIST", b"odd"), after=chunk(b"id3 ", b"tags"))
        self.assertEqual(uncompressed.wav_samples(data), [expected])
        with self.assertRaises(uncompressed.FormatError):
            uncompressed.wav_samples(wav(format_tag=2)[0])  # ADPCM

    def test_aiff(self):
        for kind, compression in ((b"AIFF", b""), (b"AIFC", b"NONE"), (b"AIFC", b"twos")):
            data, expected = aiff(kind, compression)
            self.assertEqual(uncompressed.aiff_samples(data), [expected])
        with self.assertRaises(uncompressed.FormatError):
            uncompressed.aiff_samples(aiff(b"AIFC", b"ima4")[0])

    def test_only_the_data_changes(self):
        for data, (start, end) in (bmp(), wav(after=chunk(b"id3 ", b"tags")), aiff()):
            for seed in range(3):
                out = engine.glitch(data, OPS, seed=seed, target="auto")
                self.assertEqual((out[:start], out[end:]), (data[:start], data[end:]))
                self.assertNotEqual(out[start:end], data[start:end])

    def test_auto_picks_by_file_type(self):
        self.assertEqual(engine.detect_target(bmp()[0]), "bmp-pixels")
        self.assertEqual(engine.detect_target(b"P6\n1 1\n255\n..."), "ppm-pixels")
        self.assertEqual(engine.detect_target(wav()[0]), "wav-samples")
        self.assertEqual(engine.detect_target(aiff()[0]), "aiff-samples")
        self.assertEqual(engine.detect_target(b"\xff\xd8\xff"), "jpeg-scan")
        self.assertEqual(engine.detect_target(b"GIF89a"), "all")
        with self.assertRaises(engine.GlitchError):  # a known format that can't be used isn't silently treated as "all"
            engine.glitch(wav(format_tag=2)[0], OPS, target="auto")

if __name__ == "__main__":
    unittest.main()
