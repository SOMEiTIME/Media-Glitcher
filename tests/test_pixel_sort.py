import os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import engine, media_glitcher, pixel_sort, presets

try:
    import numpy as np
except ImportError:
    np = None

def ffmpeg_works():
    try:
        return subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False

def op(key="brightness", low=0.0, high=1.0, angle=0.0):
    return {"type": "pixel-sort", "key": key, "low": low, "high": high, "angle": angle}

class PresetTest(unittest.TestCase):
    def test_checks_key_and_threshold(self):
        self.assertEqual(presets.check_operation(op("hue", 0.2, 0.8, 90)), op("hue", 0.2, 0.8, 90))
        with self.assertRaisesRegex(presets.PresetError, "key must be one of"):
            presets.check_operation(op("value"))
        with self.assertRaisesRegex(presets.PresetError, "low must be at least 0"):
            presets.check_operation(op(low=-0.5))

    def test_flag_parses_into_operation(self):
        parse, metavar = media_glitcher.operation_arg("pixel-sort")
        self.assertEqual(metavar, "KEY,LOW,HIGH,ANGLE")
        self.assertEqual(parse("saturation,0.1,0.9,-45"), op("saturation", 0.1, 0.9, -45.0))

@unittest.skipUnless(np, "needs NumPy")
class PixelSortTest(unittest.TestCase):
    def setUp(self):
        self.frame = np.random.RandomState(0).randint(0, 256, (37, 53, 3)).astype(np.uint8)

    def brightness(self, pixels):
        return pixel_sort.sort_key(pixels, "brightness")

    def test_keeps_shape_and_dtype(self):
        for key in pixel_sort.KEYS:
            for angle in (0, 90, 30, 200):
                out = pixel_sort.pixel_sort(self.frame, key, 0.2, 0.8, angle)
                self.assertEqual((out.shape, out.dtype), (self.frame.shape, self.frame.dtype))

    def test_no_pixels_in_threshold_leaves_frame_unchanged(self):
        for low, high in ((2, 3), (0.8, 0.2)):
            out = pixel_sort.pixel_sort(self.frame, "brightness", low, high, 30)
            self.assertTrue((out == self.frame).all())

    def test_same_input_gives_same_output(self):
        a = pixel_sort.pixel_sort(self.frame, "hue", 0.1, 0.9, 30)
        b = pixel_sort.pixel_sort(self.frame.copy(), "hue", 0.1, 0.9, 30)
        self.assertTrue((a == b).all())

    def test_only_moves_pixels_around(self):
        out = pixel_sort.pixel_sort(self.frame, "saturation", 0.3, 0.9, 137)
        self.assertFalse((out == self.frame).all())
        rows = lambda f: sorted(map(tuple, f.reshape(-1, 3)))
        self.assertEqual(rows(out), rows(self.frame))

    def test_sorts_rows_columns_and_reversed_rows(self):
        def ascending(lines):
            keys = self.brightness(lines)
            return (keys[:, 1:] >= keys[:, :-1]).all()
        self.assertTrue(ascending(pixel_sort.pixel_sort(self.frame, "brightness", 0, 1, 0)))
        self.assertTrue(ascending(pixel_sort.pixel_sort(self.frame, "brightness", 0, 1, 90).transpose(1, 0, 2)))
        self.assertTrue(ascending(pixel_sort.pixel_sort(self.frame, "brightness", 0, 1, 180)[:, ::-1]))

    def test_sorts_only_runs_inside_threshold(self):
        out = pixel_sort.pixel_sort(self.frame, "brightness", 0.3, 0.7, 0)
        before, after = self.brightness(self.frame), self.brightness(out)
        outside = (before < 0.3) | (before > 0.7)
        self.assertTrue((out[outside] == self.frame[outside]).all())
        for y in range(self.frame.shape[0]):
            for x in range(1, self.frame.shape[1]):
                if not outside[y, x] and not outside[y, x - 1]:
                    self.assertGreaterEqual(after[y, x], after[y, x - 1])

    def test_keys_of_primary_colours(self):
        red_green_blue_grey = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [128, 128, 128]]], np.uint8)
        key = lambda name: pixel_sort.sort_key(red_green_blue_grey, name)[0].round(3).tolist()
        self.assertEqual(key("hue"), [0, 0.333, 0.667, 0])
        self.assertEqual(key("saturation"), [1, 1, 1, 0])
        self.assertEqual(key("g"), [0, 1, 0, 0.502])
        self.assertEqual(key("brightness"), [0.299, 0.587, 0.114, 0.502])

@unittest.skipUnless(np, "needs NumPy")
class ImageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        frame = np.random.RandomState(1).randint(0, 256, (20, 30, 3)).astype(np.uint8)
        self.ppm = b"P6\n# made by a test\n30 20\n255\n" + frame.tobytes()
        self.frame = frame

    def test_ppm_round_trip_through_cli(self):
        source, out = os.path.join(self.dir.name, "in.ppm"), os.path.join(self.dir.name, "out.ppm")
        with open(source, "wb") as f:
            f.write(self.ppm)
        media_glitcher.main([source, out, "-q", "--pixel-sort", "brightness,0.2,0.9,90"])
        with open(out, "rb") as f:
            result = f.read()
        expected = pixel_sort.pixel_sort(self.frame, "brightness", 0.2, 0.9, 90)
        self.assertEqual(result, b"P6\n30 20\n255\n" + expected.tobytes())

    def test_mixes_with_byte_operations(self):
        ops = [op(), {"type": "bitflip", "rate": 0.01}]
        result = engine.glitch(self.ppm, ops, seed=3, target="ppm-pixels")
        self.assertEqual(result, engine.glitch(self.ppm, ops, seed=3, target="ppm-pixels"))
        self.assertEqual(len(result), len(b"P6\n30 20\n255\n") + self.frame.size)

    def test_refuses_short_ppm(self):
        with self.assertRaisesRegex(engine.GlitchError, "can't use pixel-sort: PPM is shorter"):
            engine.glitch(self.ppm[:-1], [op()])

    def test_keeps_16_bit_depth(self):
        # times 257 maps 0..255 onto 0..65535, so the keys and the sort are the same as in 8-bit
        deep = (self.frame.astype(">u2") * 257).tobytes()
        result = engine.glitch(b"P6\n30 20\n65535\n" + deep, [op(angle=90)])
        expected = pixel_sort.pixel_sort(self.frame, "brightness", 0, 1, 90).astype(">u2") * 257
        self.assertEqual(result, b"P6\n30 20\n65535\n" + expected.tobytes())

    @unittest.skipUnless(ffmpeg_works(), "needs a working ffmpeg")
    def test_jpeg_stays_jpeg(self):
        with open(os.path.join(HERE, "fixtures", "baseline.jpg"), "rb") as f:
            data = f.read()
        result = engine.glitch(data, [op(low=0.3, high=0.8)])
        self.assertTrue(result.startswith(b"\xff\xd8"))
        frame, _ = pixel_sort.decode(result)
        self.assertEqual(frame.shape, pixel_sort.decode(data)[0].shape)

    @unittest.skipIf(ffmpeg_works(), "only for when ffmpeg is missing or broken")
    def test_explains_missing_ffmpeg(self):
        with self.assertRaisesRegex(engine.GlitchError, "can't use pixel-sort: .*ffmpeg"):
            engine.glitch(b"\x89PNG\r\n\x1a\n" + bytes(100), [op()])

    def test_refuses_unknown_formats(self):
        with self.assertRaisesRegex(engine.GlitchError, "works on JPEG, PNG, BMP and PPM"):
            engine.glitch(b"GIF89a" + bytes(100), [op()])

if __name__ == "__main__":
    unittest.main()
