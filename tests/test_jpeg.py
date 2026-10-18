import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import engine, jpeg, media_glitcher, presets

def fixture(name):
    with open(os.path.join(HERE, "fixtures", name + ".jpg"), "rb") as f:
        return f.read()

BASELINE = fixture("baseline")
SCAN_OPS = [{"type": "byte-swap", "size": 32, "every": 600}, {"type": "byte-corrupt", "every": 300},
            {"type": "bitflip", "rate": 0.001}, {"type": "repeat", "size": 40, "every": 1500}]
TABLE_OPS = [{"type": "byte-corrupt", "every": 4}, {"type": "bitflip", "rate": 0.1}]

# an iPhone-style file: a whole JPEG thumbnail inside an APP1 segment, and a second image after the end
def iphone_like():
    app1 = b"Exif\x00\x00" + BASELINE
    return BASELINE[:2] + b"\xff\xe1" + (len(app1) + 2).to_bytes(2, "big") + app1 + BASELINE[2:] + BASELINE

def changed_positions(a, b):
    return {i for i, (x, y) in enumerate(zip(a, b)) if x != y}

def inside(ranges):
    return {i for start, end in ranges for i in range(start, end)}

class ParserTest(unittest.TestCase):
    def test_segments(self):
        markers = [m for m, _, _ in jpeg.segments(BASELINE)]
        self.assertEqual(markers[:3], [0xE0, jpeg.DQT, jpeg.DQT])
        self.assertEqual(markers[-2:], [jpeg.SOS, jpeg.SCAN])
        self.assertEqual(len(jpeg.scan_ranges(fixture("progressive"))), 10)
        self.assertEqual(sum(e - s for s, e in jpeg.table_ranges(BASELINE)), 128)

    def test_scan_ends_at_the_next_real_marker(self):
        for name in ("baseline", "progressive", "restarts"):
            data = fixture(name)
            for start, end in jpeg.scan_ranges(data):
                self.assertEqual(data[end], 0xFF)
                self.assertNotIn(data[end + 1], (0, *jpeg.RESTARTS))

    def test_embedded_thumbnail_and_trailing_image_are_skipped(self):
        data = iphone_like()
        self.assertEqual(len(jpeg.scan_ranges(data)), 1)
        start, end = jpeg.scan_ranges(data)[0]
        self.assertGreater(start, len(BASELINE))           # after the thumbnail
        self.assertLess(end, len(data) - len(BASELINE))    # before the trailing image

    def test_not_a_jpeg(self):
        with self.assertRaises(jpeg.JpegError):
            jpeg.segments(b"PNG not a jpeg")
        with self.assertRaises(engine.GlitchError):
            engine.glitch(b"\x89PNG" + bytes(5000), SCAN_OPS, target="jpeg-scan")

    def test_repair_scan(self):
        data = bytearray(b"\xff\x12" b"\xff\x00" b"\xff\xd3" b"\x10\xff")
        jpeg.repair_scan(data, [(0, len(data))])
        self.assertEqual(data, bytearray(b"\xfe\x12" b"\xff\x00" b"\xff\xd3" b"\x10\xfe"))

    def test_repair_tables(self):
        data = bytearray(b"\x00" + bytes(4) + b"\x10" + bytes([0, 0, 0, 7]))
        jpeg.repair_tables(data, [(1, 5), (6, 10)])
        self.assertEqual(data, bytearray(b"\x00\x01\x01\x01\x01\x10\x00\x01\x00\x07"))

class TargetTest(unittest.TestCase):
    def test_scan_target_only_changes_image_data_and_keeps_structure(self):
        for name, data in (("baseline", BASELINE), ("progressive", fixture("progressive")),
                           ("restarts", fixture("restarts")), ("iphone-like", iphone_like())):
            for seed in range(5):
                with self.subTest(file=name, seed=seed):
                    out = engine.glitch(data, SCAN_OPS, seed=seed, target="jpeg-scan")
                    self.assertEqual(len(out), len(data))
                    self.assertTrue(changed_positions(data, out) <= inside(jpeg.scan_ranges(data)))
                    self.assertEqual(jpeg.segments(out), jpeg.segments(data))

    def test_tables_target_only_changes_table_values(self):
        for seed in range(5):
            out = engine.glitch(BASELINE, TABLE_OPS, seed=seed, target="jpeg-tables")
            ranges = jpeg.table_ranges(BASELINE)
            self.assertTrue(changed_positions(BASELINE, out) <= inside(ranges))
            self.assertNotIn(0, [out[i] for i in inside(ranges)])

    def test_target_flag_and_preset(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        saved = os.path.join(directory.name, "p.json")
        media_glitcher.main(["--save-preset", saved, "--bitflip", "0.01", "--target", "jpeg-tables", "-q"])
        loaded = presets.load(saved)
        self.assertEqual((loaded["target"], "header_bytes" in loaded), ("jpeg-tables", False))
        with self.assertRaises(presets.PresetError):
            presets.validate({"target": "png", "operations": SCAN_OPS})

if __name__ == "__main__":
    unittest.main()
