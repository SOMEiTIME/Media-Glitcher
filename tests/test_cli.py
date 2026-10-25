import contextlib, io, json, os, random, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine, media_glitcher, presets

# runs the CLI with its output (usage errors, "Saved preset") hidden
def main(args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        media_glitcher.main(args)

def swap(interval, flavour):
    return {"type": "swap", "interval": interval, "flavour": flavour}

class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        rng = random.Random(0)
        self.source = self.path("in.bin")
        with open(self.source, "wb") as f:
            f.write(bytes(rng.randrange(256) for _ in range(200000)))

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def run_cli(self, out, *args):
        main([self.source, self.path(out), "-q", *args])
        with open(self.path(out), "rb") as f:
            return f.read()

    def test_bundled_presets_are_valid(self):
        found = presets.list_presets()
        self.assertTrue({"default", "recommended", "classic", "swaps-frequent", "swaps-sparse",
                         "corrupt-escalating"} <= {name for name, _ in found})
        for name, description in found:
            presets.load(name)
            self.assertFalse(description.startswith("(invalid"), name)

    def test_recommended_parts_cover_recommended(self):
        parts = []
        for name in ("swaps-sparse", "swaps-frequent", "corrupt-escalating"):
            parts += presets.load(name)["operations"]
        key = lambda op: json.dumps(op, sort_keys=True)
        self.assertEqual(sorted(parts, key=key), sorted(presets.load("recommended")["operations"], key=key))

    def test_seeded_run_is_reproducible(self):
        a = self.run_cli("a", "--preset", "recommended", "--seed", "7")
        b = self.run_cli("b", "--preset", "recommended", "--seed", "7")
        self.assertEqual(a, b)
        with open(self.source, "rb") as f:
            self.assertNotEqual(a, f.read())

    def test_preset_equals_flags(self):
        flags = ["--swap", "200,50", "--swap", "100,3", "--corrupt", "200,30",
                 "--corrupt", "400,3", "--swap", "40,3", "--seed", "3"]
        self.assertEqual(self.run_cli("a", "--preset", "recommended", "--seed", "3"),
                         self.run_cli("b", *flags))

    def test_save_then_load_round_trip(self):
        saved = self.path("mine.json")
        main(["--save-preset", saved, "--swap", "50,2", "--corrupt", "300,5",
                             "--seed", "9", "--header-length", "0", "--description", "test", "-q"])
        loaded = presets.load(saved)
        self.assertEqual(loaded["operations"], [swap(50, 2), {"type": "corrupt", "interval": 300, "flavour": 5}])
        self.assertEqual((loaded["seed"], loaded["header_length"], loaded["description"]), (9, 0, "test"))
        self.assertEqual(self.run_cli("a", "--preset", saved), self.run_cli("b", "--swap", "50,2",
                         "--corrupt", "300,5", "--seed", "9", "--header-length", "0"))

    def test_save_with_missing_output_saves_nothing(self):
        saved = self.path("half.json")
        with self.assertRaises(SystemExit):
            main([self.source, "--save-preset", saved, "--swap", "50,2"])
        self.assertFalse(os.path.exists(saved))

    def test_save_refuses_to_overwrite_without_force(self):
        saved = self.path("mine.json")
        presets.save(saved, [swap(1, 1)], description="original")
        with self.assertRaises(presets.PresetError):
            presets.save(saved, [swap(2, 2)])
        with self.assertRaises(SystemExit):
            main([self.source, self.path("o"), "--save-preset", saved, "--swap", "3,3", "-q"])
        self.assertFalse(os.path.exists(self.path("o")))
        self.assertEqual(presets.load(saved)["description"], "original")
        main(["--save-preset", saved, "--swap", "4,4", "--force", "-q"])
        self.assertEqual(presets.load(saved)["operations"], [swap(4, 4)])

    def test_command_line_overrides_preset_settings(self):
        saved = self.path("p.json")
        presets.save(saved, [swap(50, 2)], header_length=0, seed=1)
        self.assertEqual(self.run_cli("a", "--preset", saved, "--seed", "2"),
                         self.run_cli("b", "--swap", "50,2", "--seed", "2", "--header-length", "0"))

    def test_invalid_presets_rejected(self):
        bad = [{}, {"operations": []}, {"operations": [{"type": "nope", "interval": 1, "flavour": 1}]},
               {"operations": [{"type": "swap", "interval": "1", "flavour": 1}]},
               {"operations": [{"type": "swap", "interval": 1, "flavour": 1}], "extra": 1}]
        for data in bad:
            with self.assertRaises(presets.PresetError):
                presets.validate(data)
        broken = self.path("broken.json")
        with open(broken, "w") as f:
            f.write("{not json")
        with self.assertRaises(SystemExit):
            main([self.source, self.path("o"), "--preset", broken])

class ByteModeTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(1)
        self.data = bytes(rng.randrange(256) for _ in range(50000))

    def test_byte_operations_keep_length_and_header(self):
        for op in ({"type": "byte-swap", "size": 64, "every": 1000}, {"type": "byte-corrupt", "every": 100},
                   {"type": "bitflip", "rate": 0.001}, {"type": "repeat", "size": 32, "every": 2000}):
            with self.subTest(op=op["type"]):
                out = engine.glitch(self.data, [op], header_bytes=4096, seed=3)
                self.assertEqual(len(out), len(self.data))
                self.assertEqual(out[:4096], self.data[:4096])
                self.assertNotEqual(out, self.data)

    def test_bitflip_flips_the_requested_share_of_bits(self):
        out = engine.glitch(self.data, [{"type": "bitflip", "rate": 0.001}], header_bytes=0, seed=4)
        flipped = sum(bin(a ^ b).count("1") for a, b in zip(self.data, out))
        # 400 flips requested; a bit picked twice flips back, so allow a little less
        self.assertTrue(380 <= flipped <= 400, flipped)

    def test_seed_reproduces_and_modes_mix(self):
        ops = [swap(100, 3), {"type": "byte-swap", "size": 16, "every": 500}, swap(40, 3)]
        self.assertEqual(engine.glitch(self.data, ops, seed=5), engine.glitch(self.data, ops, seed=5))
        self.assertNotEqual(engine.glitch(self.data, ops, seed=5), engine.glitch(self.data, ops, seed=6))

    def test_file_smaller_than_byte_header_is_an_error(self):
        with self.assertRaises(engine.GlitchError):
            engine.glitch(self.data[:100], [{"type": "byte-corrupt", "every": 10}], header_bytes=100)

    def test_byte_flags_and_preset_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            source, out, saved = (os.path.join(directory, name) for name in ("in", "out", "p.json"))
            with open(source, "wb") as f:
                f.write(self.data)
            main([source, out, "-q", "--byte-swap", "64,1000", "--bitflip", "0.0005",
                                 "--header-bytes", "2048", "--seed", "1", "--save-preset", saved])
            loaded = presets.load(saved)
            self.assertEqual((loaded["header_bytes"], "header_length" in loaded), (2048, False))
            with open(out, "rb") as f:
                expected = engine.glitch(self.data, loaded["operations"], header_bytes=2048, seed=1)
                self.assertEqual(f.read(), expected)

    def test_bad_byte_flags_rejected(self):
        for args in (["--byte-swap", "64"], ["--byte-swap", "0,10"], ["--bitflip", "x"], ["--byte-corrupt", "1.5"]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                main(["in", "out"] + args)

if __name__ == "__main__":
    unittest.main()
