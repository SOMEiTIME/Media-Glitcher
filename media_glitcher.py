#!/usr/bin/env python3

# Command line entry point for running the media class and glitching media

import argparse, random, sys
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

# argparse action that records operations in the order they appear on the command line
class AddOperation(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        operations = getattr(namespace, "operations", None) or []
        if self.dest == "preset":
            operations.extend(values["operations"])
            settings = getattr(namespace, "preset_settings", None) or {}
            settings.update({k: v for k, v in values.items() if k in ("header_length", "seed")})
            namespace.preset_settings = settings
        else:
            operations.append((self.dest,) + values)
        namespace.operations = operations

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
                        help="add the operations from a preset: a name, group/name (groups: user, builtin, test) or .json path. "
                             "Its header_length and seed apply unless given as options")
    parser.add_argument("--list-presets", action="store_true", help="list the available presets and exit")
    parser.add_argument("--save-preset", metavar="NAME_OR_FILE",
                        help="write this run's settings to a preset (a bare name goes in presets/user/); "
                             "with no file arguments, saves without glitching anything")
    parser.add_argument("--description", default="", help="description to store with --save-preset")
    parser.add_argument("--header-length", type=int, metavar="LINES",
                        help="lines at the start of the file left untouched; "
                             "15 is good for video, 0 may be fine for images (default: %d)" % DEFAULT_HEADER_LENGTH)
    parser.add_argument("--seed", type=int, help="random seed, for reproducible output")
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print the file names")
    return parser

def main(argv=None):
    parser = build_parser()
    parser.set_defaults(operations=None, preset_settings={})
    args = parser.parse_args(argv)

    if args.list_presets:
        shown = None
        for group, name, description in presets.list_presets():
            if group != shown:
                print("%s%s presets:" % ("\n" if shown else "", group))
                shown = group
            print("  %-22s %s" % (name, description))
        return

    try:
        default = presets.load(DEFAULT_PRESET)
    except presets.PresetError as error:
        parser.error(str(error))
    operations = args.operations or default["operations"]
    header_length = first_set(args.header_length, args.preset_settings.get("header_length"),
                              None if args.operations else default.get("header_length"), DEFAULT_HEADER_LENGTH)
    seed = first_set(args.seed, args.preset_settings.get("seed"))
    if header_length < 0:
        parser.error("--header-length must not be negative")

    if args.save_preset:
        path = presets.save(args.save_preset, operations, header_length, seed, args.description)
        if not args.quiet:
            print("Saved preset: ", path)
        if args.input_file is None:
            return
    if args.input_file is None or args.output_file is None:
        parser.error("input_file and output_file are required")
    if args.input_file == args.output_file:
        parser.error("input and output files must be different")
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

# first argument that isn't None
def first_set(*values):
    return next((v for v in values if v is not None), None)

if __name__ == "__main__":
    main()
