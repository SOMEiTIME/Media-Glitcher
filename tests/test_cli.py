import json, os, random, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import media_glitcher, presets

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
        media_glitcher.main([self.source, self.path(out), "-q", *args])
        with open(self.path(out), "rb") as f:
            return f.read()

    def test_bundled_presets_are_valid(self):
        found = presets.list_presets()
        builtin = {name for group, name, _ in found if group == "builtin"}
        self.assertEqual(builtin, {"default", "recommended", "classic"})
        for group, name, description in found:
            presets.load(group + "/" + name)
            self.assertFalse(description.startswith("(invalid"), name)

    def test_groups_save_and_lookup(self):
        original = presets.PRESET_DIR
        presets.PRESET_DIR = self.path("presets")
        self.addCleanup(setattr, presets, "PRESET_DIR", original)
        for group in ("builtin", "user"):
            os.makedirs(self.path("presets/" + group))
        presets.save("builtin/shared", [("swap", 1, 1)], description="builtin one")
        # a bare name saves to the user group and shadows the builtin of the same name
        saved = presets.save("shared", [("corrupt", 2, 2)], description="user one")
        self.assertEqual(saved, self.path("presets/user/shared.json"))
        self.assertEqual(presets.load("shared")["description"], "user one")
        self.assertEqual(presets.load("builtin/shared")["description"], "builtin one")
        self.assertEqual([g for g, n, _ in presets.list_presets()], ["user", "builtin"])

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
        media_glitcher.main(["--save-preset", saved, "--swap", "50,2", "--corrupt", "300,5",
                             "--seed", "9", "--header-length", "0", "--description", "test", "-q"])
        loaded = presets.load(saved)
        self.assertEqual(loaded["operations"], [("swap", 50, 2), ("corrupt", 300, 5)])
        self.assertEqual((loaded["seed"], loaded["header_length"], loaded["description"]), (9, 0, "test"))
        self.assertEqual(self.run_cli("a", "--preset", saved), self.run_cli("b", "--swap", "50,2",
                         "--corrupt", "300,5", "--seed", "9", "--header-length", "0"))

    def test_command_line_overrides_preset_settings(self):
        saved = self.path("p.json")
        presets.save(saved, [("swap", 50, 2)], header_length=0, seed=1)
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
            media_glitcher.main([self.source, self.path("o"), "--preset", broken])

if __name__ == "__main__":
    unittest.main()
