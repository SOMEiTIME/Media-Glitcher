import hashlib, json, os, random, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import media_glitcher

# Golden-output cases: each one runs a preset on a generated input and compares
# the SHA-256 of the result to the one recorded in cases.json. A failure means the
# glitch output changed. If that was intended, regenerate with:
#   python3 tests/test_golden.py --update
# Hashes depend on Python's random module, so regenerate if they differ on another Python version.
CASES_FILE = os.path.join(HERE, "cases.json")

def make_input(path, size, seed):
    rng = random.Random(seed)
    with open(path, "wb") as f:
        f.write(bytes(rng.randrange(256) for _ in range(size)))

# Runs one case and returns the SHA-256 hex digest of the output file
def run_case(case, directory):
    source = os.path.join(directory, "in.bin")
    output = os.path.join(directory, "out.bin")
    make_input(source, case["input_size"], case["input_seed"])
    media_glitcher.main([source, output, "--preset", case["preset"], "-q"])
    with open(output, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def load_cases():
    with open(CASES_FILE, encoding="utf-8") as f:
        return json.load(f)

class GoldenTest(unittest.TestCase):
    def test_cases(self):
        for case in load_cases():
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as directory:
                self.assertEqual(run_case(case, directory), case["sha256"])

def update():
    cases = load_cases()
    for case in cases:
        with tempfile.TemporaryDirectory() as directory:
            case["sha256"] = run_case(case, directory)
        print("%-24s %s" % (case["name"], case["sha256"]))
    with open(CASES_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)
        f.write("\n")

if __name__ == "__main__":
    if "--update" in sys.argv:
        update()
    else:
        unittest.main()
