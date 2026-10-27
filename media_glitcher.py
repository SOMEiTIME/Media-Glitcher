#!/usr/bin/env python3

# Command line entry point for glitching media

import argparse, os, signal, sys
import engine, pixel_sort, presets, preview

DEFAULT_PRESET = "default" # run when no operations are given
SETTINGS = ("header_length", "header_bytes", "seed", "target") # preset fields the command line can override

# help text for each operation flag; the parameters come from engine.OPERATIONS
OPERATION_HELP = {
    "swap": "line mode: swap lines, about once every INTERVAL lines",
    "corrupt": "line mode: swap lines further apart the further into the file, once every INTERVAL lines",
    "byte-swap": "byte mode: swap a SIZE-byte chunk with a nearby one, once every EVERY bytes",
    "byte-corrupt": "byte mode: replace one byte with a random value, once every EVERY bytes",
    "bitflip": "byte mode: flip a RATE fraction of the bits, e.g. 0.0001",
    "repeat": "byte mode: copy a SIZE-byte chunk over the next one, once every EVERY bytes",
    "iframe-drop": "frame mode (MPEG-4 AVI): datamosh by removing every keyframe after the first KEEP",
    "pframe-repeat": "frame mode (MPEG-4 AVI): once every EVERY video frames, repeat a P-frame COUNT more times",
    "pixel-sort": "pixel mode (JPEG, PNG, BMP, PPM, MP4, MOV, AVI; needs NumPy, and ffmpeg for all but PPM): sort runs of pixels "
                  "whose KEY (%s) is from LOW to HIGH (0 to 1), along lines at ANGLE degrees "
                  "(0 left to right, 90 top to bottom, 180 right to left)" % ", ".join(pixel_sort.KEYS),
}

#
# argparse type for an operation flag: turns e.g. "64,5000" into
# {"type": "byte-swap", "size": 64, "every": 5000}, checked like a preset operation
#
def operation_arg(op_type):
    params = engine.OPERATIONS[op_type]
    metavar = ",".join(name.upper() for name, _, _ in params)
    def parse(text):
        parts = text.split(",")
        usage = argparse.ArgumentTypeError("expected %s, got '%s'" % (metavar, text))
        if len(parts) != len(params):
            raise usage
        try:
            op = {"type": op_type, **{name: part if isinstance(kind, tuple) else kind(part)
                                      for (name, kind, _), part in zip(params, parts)}}
        except ValueError:
            raise usage
        try:
            return presets.check_operation(op)
        except presets.PresetError as error:
            raise argparse.ArgumentTypeError(str(error))
    return parse, metavar

# argparse type for --preset, loads the preset up front so errors show as usage errors
def preset_arg(text):
    try:
        return presets.load(text)
    except presets.PresetError as error:
        raise argparse.ArgumentTypeError(str(error))

# the settings in a preset that the command line can override
def preset_settings(preset):
    return {k: v for k, v in preset.items() if k in SETTINGS and v is not None}

# argparse action that records operations in the order they appear on the command line
class AddOperation(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if self.dest == "preset":
            new = values["operations"]
            namespace.preset_settings = {**namespace.preset_settings, **preset_settings(values)}
        else:
            new = [values]
        namespace.operations = namespace.operations + new

# where the output goes when none is given: NAME-glitched.EXT beside the input
def default_output(input_file):
    stem, ext = os.path.splitext(input_file)
    return stem + "-glitched" + ext

# first argument that isn't None
def first_set(*values):
    return next((v for v in values if v is not None), None)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Glitch a media file by swapping and corrupting its raw data, by lines or by bytes.",
        epilog="Operations run in the order given. With none given, the '%s' preset is used." % DEFAULT_PRESET)
    parser.add_argument("input_file", nargs="?", help="file to glitch")
    parser.add_argument("output_file", nargs="?",
                        help="where to write the glitched file, overwritten (default: NAME-glitched.EXT next to the input)")
    for op_type in engine.OPERATIONS:
        parse, metavar = operation_arg(op_type)
        parser.add_argument("--" + op_type, metavar=metavar, type=parse, action=AddOperation,
                            help=OPERATION_HELP[op_type] + " (repeatable)")
    parser.add_argument("--preset", metavar="NAME_OR_FILE", type=preset_arg, action=AddOperation,
                        help="add the operations from a preset, by name (from presets/) or .json path. "
                             "Its headers and seed apply unless given as options")
    parser.add_argument("--list-presets", action="store_true", help="list the available presets and exit")
    parser.add_argument("--save-preset", metavar="NAME_OR_FILE",
                        help="write this run's settings to a preset file; with no file arguments, "
                             "saves without glitching anything")
    parser.add_argument("--description", default="", help="description to store with --save-preset")
    parser.add_argument("--force", action="store_true", help="let --save-preset replace an existing preset")
    parser.add_argument("--header-length", type=int, metavar="LINES",
                        help="lines at the start of the file left untouched by line operations; "
                             "15 is good for video, 0 may be fine for images (default: %d)" % engine.DEFAULT_HEADER_LENGTH)
    parser.add_argument("--header-bytes", type=int, metavar="BYTES",
                        help="bytes at the start of the file left untouched by byte operations "
                             "(default: %d)" % engine.DEFAULT_HEADER_BYTES)
    parser.add_argument("--target", choices=engine.TARGETS,
                        help="part of the file byte operations change: all is everything after --header-bytes, "
                             "auto picks one from the file type (default: %s)" % engine.DEFAULT_TARGET)
    parser.add_argument("--seed", type=int, help="random seed, for reproducible output")
    parser.add_argument("--preview", action=argparse.BooleanOptionalAction,
                        help="print the output as text afterwards (default: on in a terminal without -q), drawn with "
                             "a repeating word, the damage in red with its case swapped; video plays until it ends or Ctrl-C (ffmpeg for all but BMP and "
                             "PPM, otherwise a map of the damaged bytes)")
    parser.add_argument("--preview-word", metavar="WORD", help="word the preview is drawn with (default: the output file's name, or %s "
                             "if none was given)" % preview.DEFAULT_WORD)
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="don't print the file names, video progress or (unless --preview) the preview")
    return parser

#
# Shows how far a video's pixel sort has got on one line of stderr, rewritten
# for each frame and erased when done. Images (one frame) show nothing
#
class Progress:
    def __init__(self):
        self.width = 0

    def __call__(self, done, total):
        if total == 1:
            return
        line = "pixel sorting frame %d/%s" % (done, total or "?")
        self.width = max(self.width, len(line))
        sys.stderr.write("\r" + line)
        sys.stderr.flush()

    def clear(self):
        if self.width:
            sys.stderr.write("\r%s\r" % (" " * self.width))
            sys.stderr.flush()

def main(argv=None):
    parser = build_parser()
    parser.set_defaults(operations=[], preset_settings={})
    args = parser.parse_args(argv)

    if args.list_presets:
        for name, description in presets.list_presets():
            print("%-20s %s" % (name, description))
        return

    operations, settings = args.operations, args.preset_settings
    if not operations:
        try:
            default = presets.load(DEFAULT_PRESET)
        except presets.PresetError as error:
            parser.error(str(error))
        operations, settings = default["operations"], preset_settings(default)
    header_length = first_set(args.header_length, settings.get("header_length"), engine.DEFAULT_HEADER_LENGTH)
    header_bytes = first_set(args.header_bytes, settings.get("header_bytes"), engine.DEFAULT_HEADER_BYTES)
    seed = first_set(args.seed, settings.get("seed"))
    target = first_set(args.target, settings.get("target"), engine.DEFAULT_TARGET)
    if header_length < 0:
        parser.error("--header-length must not be negative")
    if header_bytes < 0:
        parser.error("--header-bytes must not be negative")

    # --save-preset on its own only saves; otherwise an input file is needed
    glitching = args.input_file is not None or not args.save_preset
    if glitching:
        if args.input_file is None:
            parser.error("input_file is required")
        if args.output_file is None:
            args.output_file = default_output(args.input_file)
            # NAME-glitched would just repeat the input's name, so use the tool's
            if args.preview_word is None:
                args.preview_word = preview.DEFAULT_WORD
        if args.input_file == args.output_file:
            parser.error("input and output files must be different")
    # checked before glitching, so a refused save doesn't leave a half-finished run
    if args.save_preset and not args.force and os.path.exists(presets.resolve(args.save_preset)):
        parser.error("preset %s already exists, add --force to replace it" % presets.resolve(args.save_preset))

    if args.save_preset:
        # only store the header settings the operations actually use
        uses_lines = any(engine.is_line_operation(op) for op in operations)
        uses_bytes = any(engine.is_byte_operation(op) for op in operations)
        try:
            path = presets.save(args.save_preset, operations, seed=seed, description=args.description,
                                header_length=header_length if uses_lines else None,
                                header_bytes=header_bytes if uses_bytes and target == "all" else None,
                                target=target if uses_bytes and target != "all" else None, overwrite=args.force)
        except (OSError, presets.PresetError) as error:
            parser.exit(1, "error: cannot save preset: %s\n" % error)
        # printed even with -q, so a mistyped name is noticed straight away
        print("Saved preset: ", path)
    if not glitching:
        return

    if not args.quiet:
        print("Input File: ", args.input_file)
        print("Output File: ", args.output_file)

    try:
        with open(args.input_file, "rb") as file:
            data = file.read()
    except OSError as error:
        parser.exit(1, "error: %s\n" % error)
    # progress only goes to a terminal, so piped or logged output stays clean
    progress = Progress() if not args.quiet and sys.stderr.isatty() else None
    try:
        try:
            data = engine.glitch(data, operations, header_length, header_bytes, seed, target, progress)
        finally:
            if progress:
                progress.clear()  # before any error, so it isn't printed on the progress line
    except engine.GlitchError as error:
        parser.exit(1, "error: %s\n" % error)
    with open(args.output_file, "wb") as file:
        file.write(data)
    # colour and playback only on a terminal, so piped output is plain text
    terminal = sys.stdout.isatty()
    if first_set(args.preview, terminal and not args.quiet):
        preview.show(args.input_file, args.output_file, sys.stdout, args.preview_word,
                     color=terminal and "NO_COLOR" not in os.environ, animate=terminal)

#
# Runs main, exiting quietly on Ctrl-C (no traceback) and treating SIGTERM
# (e.g. from timeout) like it, so ffmpeg is stopped and temporary files are
# removed either way. Not part of main, so importing this changes no signals
#
def run():
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(128 + signal.SIGINT)

if __name__ == "__main__":
    run()
