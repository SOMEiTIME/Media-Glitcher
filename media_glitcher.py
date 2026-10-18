#!/usr/bin/env python3

# Command line entry point for running the media class and glitching media

import argparse, os, random
import presets
from media import media

# used when neither the command line nor a preset sets them
DEFAULT_HEADER_LENGTH = 15 # messing with the headers will just break the media
DEFAULT_PRESET = "default" # run when no operations are given

# argparse type for INTERVAL,FLAVOUR values
def interval_flavour(text):
    try:
        interval, flavour = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected INTERVAL,FLAVOUR (two integers), got '%s'" % text)
    if interval < 0:
        raise argparse.ArgumentTypeError("INTERVAL must not be negative")
    return interval, flavour

# argparse type for --preset, loads the preset up front so errors show as usage errors
def preset_arg(text):
    try:
        return presets.load(text)
    except presets.PresetError as error:
        raise argparse.ArgumentTypeError(str(error))

# header_length and seed from a preset, the settings the command line can override
def preset_settings(preset):
    return {k: v for k, v in preset.items() if k in ("header_length", "seed") and v is not None}

# argparse action that records operations in the order they appear on the command line
class AddOperation(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if self.dest == "preset":
            new = values["operations"]
            namespace.preset_settings = {**namespace.preset_settings, **preset_settings(values)}
        else:
            new = [(self.dest,) + values]
        namespace.operations = namespace.operations + new

# first argument that isn't None
def first_set(*values):
    return next((v for v in values if v is not None), None)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Glitch a media file by swapping and corrupting lines of its raw data.",
        epilog="Operations run in the order given. With none given, the '%s' preset is used." % DEFAULT_PRESET)
    parser.add_argument("input_file", nargs="?", help="file to glitch")
    parser.add_argument("output_file", nargs="?", help="where to write the glitched file (overwritten)")
    parser.add_argument("--swap", metavar="INTERVAL,FLAVOUR", type=interval_flavour,
                        action=AddOperation, help="add a random swap operation (repeatable)")
    parser.add_argument("--corrupt", metavar="INTERVAL,FLAVOUR", type=interval_flavour,
                        action=AddOperation, help="add a corrupt operation (repeatable)")
    parser.add_argument("--preset", metavar="NAME_OR_FILE", type=preset_arg, action=AddOperation,
                        help="add the operations from a preset, by name (from presets/) or .json path. "
                             "Its header_length and seed apply unless given as options")
    parser.add_argument("--list-presets", action="store_true", help="list the available presets and exit")
    parser.add_argument("--save-preset", metavar="NAME_OR_FILE",
                        help="write this run's settings to a preset file; with no file arguments, "
                             "saves without glitching anything")
    parser.add_argument("--description", default="", help="description to store with --save-preset")
    parser.add_argument("--force", action="store_true", help="let --save-preset replace an existing preset")
    parser.add_argument("--header-length", type=int, metavar="LINES",
                        help="lines at the start of the file left untouched; "
                             "15 is good for video, 0 may be fine for images (default: %d)" % DEFAULT_HEADER_LENGTH)
    parser.add_argument("--seed", type=int, help="random seed, for reproducible output")
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print the file names")
    return parser

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
    header_length = first_set(args.header_length, settings.get("header_length"), DEFAULT_HEADER_LENGTH)
    seed = first_set(args.seed, settings.get("seed"))
    if header_length < 0:
        parser.error("--header-length must not be negative")

    # --save-preset on its own only saves; otherwise both files are needed
    glitching = args.input_file is not None or not args.save_preset
    if glitching:
        if args.output_file is None:
            parser.error("input_file and output_file are required")
        if args.input_file == args.output_file:
            parser.error("input and output files must be different")
    # checked before glitching, so a refused save doesn't leave a half-finished run
    if args.save_preset and not args.force and os.path.exists(presets.resolve(args.save_preset)):
        parser.error("preset %s already exists, add --force to replace it" % presets.resolve(args.save_preset))

    if args.save_preset:
        try:
            path = presets.save(args.save_preset, operations, header_length, seed, args.description,
                                overwrite=args.force)
        except (OSError, presets.PresetError) as error:
            parser.exit(1, "error: cannot save preset: %s\n" % error)
        # printed even with -q, so a mistyped name is noticed straight away
        print("Saved preset: ", path)
    if not glitching:
        return

    if seed is not None:
        random.seed(seed)

    if not args.quiet:
        print("Input File: ", args.input_file)
        print("Output File: ", args.output_file)

    # latin-1 maps bytes 1:1 to characters, so binary media survives the text round trip
    try:
        with open(args.input_file, "r", encoding="latin-1", newline="") as file:
            lines = file.readlines()
    except OSError as error:
        parser.exit(1, "error: %s\n" % error)
    if len(lines) < header_length:
        parser.exit(1, "error: file has only %d lines, fewer than the header length\n" % len(lines))

    with open(args.output_file, "w", encoding="latin-1", newline="") as new_file:
        media_to_work_on = media(lines, new_file, header_length)
        presets.apply(media_to_work_on, operations)
        media_to_work_on.print_to_new_file()

if __name__ == "__main__":
    main()
