import contextlib, io, os, re, subprocess, sys, tempfile, unittest, unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import engine, media_glitcher, preview

FIXTURES = os.path.join(HERE, "fixtures")
SIZE = os.terminal_size((41, 22))

def ffmpeg_works():
    try:
        return subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False

# a 40 x 20 P6 PPM: dark left half, light right half
def ppm():
    row = bytes([10, 10, 10]) * 20 + bytes([220, 220, 220]) * 20
    return b"P6\n40 20\n255\n" + row * 20

class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, data):
        path = os.path.join(self.dir.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def show(self, before, after, name="out.ppm", **options):
        out = io.StringIO()
        options = {"word": "ab", "size": SIZE, "color": False, "animate": False, **options}
        preview.show(self.write("in", before), self.write(name, after), out, **options)
        return out.getvalue().splitlines()

class PreviewTest(Base):
    def test_word_comes_from_output_name(self):
        self.assertEqual(preview.word_for("/some/where/moshed.avi"), "moshed ")
        self.assertEqual(preview.clean_word("two words\x1b"), "twowords ")
        self.assertEqual(preview.clean_word("éé"), preview.DEFAULT_WORD + " ")

    def test_draws_picture_with_word(self):
        lines = self.show(ppm(), ppm(), word=None)
        self.assertEqual(lines[-1], "out.ppm  0% damaged")
        self.assertEqual(len(lines), 11)  # 40 x 20 pixels at two pixels high per cell, and the caption
        for line in lines[:-1]:
            self.assertEqual(len(line), 40)
            self.assertEqual(line[:20].strip(), "")  # dark half is blank
            self.assertTrue(set(line[20:]) <= set("out "))

    def test_damage_is_exact_for_raw_pixels(self):
        after = bytearray(ppm())
        after[-3] ^= 0xFF  # last pixel only
        lines = self.show(ppm(), bytes(after))
        self.assertEqual(lines[-1], "out.ppm  0% damaged")  # 1 of 400 cells rounds to 0%
        changed = [(y, x) for y, line in enumerate(lines[:-1]) for x, c in enumerate(line) if c.isupper()]
        self.assertEqual(changed, [(9, 39)])

    def test_reads_bmp(self):
        with open(os.path.join(FIXTURES, "small.bmp"), "rb") as f:
            data = f.read()
        glitched = engine.glitch(data, [{"type": "byte-corrupt", "every": 50}], seed=1, target="bmp-pixels")
        lines = self.show(data, glitched, name="out.bmp")
        self.assertRegex(lines[-1], r"^out\.bmp  [1-9]\d*% damaged$")
        self.assertTrue(any(c.isupper() for c in "".join(lines[:-1])))

    def test_colours_only_when_asked(self):
        plain = "\n".join(self.show(ppm(), ppm()))
        self.assertNotIn("\x1b", plain)
        coloured = "\n".join(self.show(ppm(), ppm(), color=True))
        self.assertIn("\x1b[38;5;", coloured)
        self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", coloured), plain)

    def test_byte_map_without_a_picture(self):
        with open(os.path.join(FIXTURES, "tone.wav"), "rb") as f:
            data = f.read()
        after = bytearray(data)
        after[-1] ^= 0xFF
        lines = self.show(data, bytes(after), name="out.wav")
        self.assertEqual(lines[-1], "out.wav  byte map  0% damaged")
        self.assertEqual(len(lines), preview.MAP_ROWS + 1)
        cells = "".join(lines[:-1])
        self.assertEqual([i for i, c in enumerate(cells) if c.isupper()], [len(cells) - 1])

    def test_byte_map_without_ffmpeg(self):
        with unittest.mock.patch("subprocess.Popen", side_effect=OSError("no ffmpeg")):
            lines = self.show(b"\x00" * 5000, b"\x00" * 4000 + b"\x01" * 1000, name="out.jpg")
        self.assertEqual(lines[-1], "out.jpg  byte map  20% damaged")

    def test_cli_prints_preview(self):
        source, output = self.write("in.ppm", ppm()), os.path.join(self.dir.name, "mine.ppm")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            media_glitcher.main([source, output, "-q", "--target", "auto", "--byte-corrupt", "100", "--seed", "1",
                                 "--preview", "--preview-word", "zz"])
        lines = out.getvalue().splitlines()
        self.assertRegex(lines[-1], r"^mine\.ppm  [1-9]\d*% damaged$")
        self.assertTrue(set("".join(lines[:-1])) <= set("zZ "))

@unittest.skipUnless(ffmpeg_works(), "needs ffmpeg")
class FfmpegPreviewTest(Base):
    def fixture(self, name):
        with open(os.path.join(FIXTURES, name), "rb") as f:
            return f.read()

    def test_jpeg_damage(self):
        data = self.fixture("baseline.jpg")
        glitched = engine.glitch(data, [{"type": "byte-corrupt", "every": 500}], seed=2, target="jpeg-scan")
        lines = self.show(data, glitched, name="out.jpg")
        self.assertRegex(lines[-1], r"^out\.jpg  [1-9]\d*% damaged$")
        self.assertEqual(self.show(data, data, name="out.jpg")[-1], "out.jpg  0% damaged")

    def test_video_prints_one_frame_when_not_animated(self):
        data = self.fixture("mpeg4.avi")
        lines = self.show(data, data, name="out.avi")
        self.assertEqual(lines[-1], "out.avi  frame 1  0% damaged")
        self.assertNotIn("\x1b", "".join(lines))

    def test_video_plays_in_place(self):
        data = self.fixture("mpeg4.avi")
        glitched = engine.glitch(data, [{"type": "pframe-repeat", "every": 5, "count": 3}], seed=1)
        out = io.StringIO()
        with unittest.mock.patch("time.sleep"):
            preview.show(self.write("in.avi", data), self.write("out.avi", glitched), out, size=SIZE, color=True)
        text = out.getvalue()
        self.assertTrue(text.startswith("\x1b[?25l") and text.endswith("\x1b[?25h"))
        frames = re.findall(r"frame (\d+)", text)
        self.assertGreater(len(frames), 20)
        self.assertEqual(frames, [str(n) for n in range(1, len(frames) + 1)])
        self.assertEqual(text.count("\x1b[%dA" % (text.split("frame 1")[0].count("\n") + 1)), len(frames) - 1)

    def test_unchanged_video_has_no_damage(self):
        data = self.fixture("mpeg4.avi")
        out = io.StringIO()
        with unittest.mock.patch("time.sleep"):
            preview.show(self.write("in.avi", data), self.write("out.avi", data), out, size=SIZE, color=False)
        self.assertEqual(set(re.findall(r"(\d+)% damaged", out.getvalue())), {"0"})

if __name__ == "__main__":
    unittest.main()
