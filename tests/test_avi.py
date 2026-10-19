import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import avi, engine, presets

# 20 frames of 64x48 MPEG-4 video with a keyframe every 5, no B-frames, plus 8-bit mono audio
with open(os.path.join(HERE, "fixtures", "mpeg4.avi"), "rb") as f:
    SOURCE = f.read()

def video(data):
    return [payload for chunk_id, payload in avi.split(data)[1] if avi.is_video(chunk_id)]

def keyframes(data):
    return [n for n, payload in enumerate(video(data)) if avi.is_keyframe(payload)]

def run(data, *operations, seed=0, target="all"):
    return engine.glitch(data, operations, seed=seed, target=target)

class AviTest(unittest.TestCase):
    def test_split_and_join_round_trip(self):
        before, frames, after = avi.split(SOURCE)
        self.assertEqual(len(video(SOURCE)), 20)
        self.assertEqual(keyframes(SOURCE), [0, 5, 10, 15])
        rebuilt = avi.join(before, frames, after)
        self.assertEqual(int.from_bytes(rebuilt[4:8], "little"), len(rebuilt) - 8)
        self.assertEqual(video(rebuilt), video(SOURCE))

    def test_iframe_drop(self):
        for keep in (1, 2, 3):
            out = run(SOURCE, {"type": "iframe-drop", "keep": keep})
            self.assertEqual(len(keyframes(out)), keep)
            self.assertEqual(len(video(out)), 20 - (4 - keep))
        out = run(SOURCE, {"type": "iframe-drop", "keep": 9})
        self.assertEqual(video(out), video(SOURCE))

    def test_pframe_repeat(self):
        out = run(SOURCE, {"type": "pframe-repeat", "every": 5, "count": 2})
        self.assertEqual(len(video(out)), 20 + 4 * 2)
        self.assertEqual(keyframes(out)[:1], [0])
        self.assertEqual(len(keyframes(out)), 4)  # keyframes are never the repeated frame

    def test_audio_is_kept(self):
        audio = lambda data: [p for i, p in avi.split(data)[1] if not avi.is_video(i)]
        out = run(SOURCE, {"type": "iframe-drop", "keep": 1}, {"type": "pframe-repeat", "every": 3, "count": 2})
        self.assertEqual(audio(out), audio(SOURCE))

    def test_seeded_and_mixed_with_byte_operations(self):
        ops = [{"type": "iframe-drop", "keep": 1}, {"type": "byte-corrupt", "every": 100},
               {"type": "pframe-repeat", "every": 4, "count": 1}]
        mosh = lambda seed: run(SOURCE, *ops, seed=seed, target="avi-frames")
        self.assertEqual(mosh(3), mosh(3))
        self.assertNotEqual(mosh(3), mosh(4))
        for seed in range(5):  # still parses after every kind of change
            avi.split(mosh(seed))

    def test_avi_frames_target_only_changes_video_payloads(self):
        ranges = avi.frame_ranges(SOURCE)
        self.assertEqual(len(ranges), 20)
        out = engine.glitch(SOURCE, [{"type": "bitflip", "rate": 0.05}], target="avi-frames", seed=1)
        self.assertEqual(len(out), len(SOURCE))
        self.assertNotEqual(out, SOURCE)
        inside = bytearray(len(SOURCE))
        for start, end in ranges:
            inside[start:end] = b"\x01" * (end - start)
        for n, (a, b) in enumerate(zip(SOURCE, out)):
            if a != b:
                self.assertTrue(inside[n], "byte %d changed outside a video frame" % n)
        self.assertEqual(engine.detect_target(SOURCE), "avi-frames")

    def test_refuses_other_files(self):
        for data in (b"RIFF\x00\x00\x00\x00WAVE" + bytes(40), bytes(range(256)) * 20, SOURCE[:300]):
            with self.assertRaises(engine.GlitchError):
                run(data, {"type": "iframe-drop", "keep": 1})
        with self.assertRaises(engine.GlitchError):
            engine.glitch(bytes(500), [{"type": "bitflip", "rate": 0.1}], target="avi-frames")

    def test_datamosh_preset(self):
        preset = presets.load("datamosh")
        self.assertEqual([op["type"] for op in preset["operations"]], ["iframe-drop", "pframe-repeat"])
        out = engine.glitch(SOURCE, preset["operations"], seed=preset["seed"])
        self.assertEqual(len(keyframes(out)), 1)

if __name__ == "__main__":
    unittest.main()
