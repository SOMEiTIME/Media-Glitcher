#!/usr/bin/env python3

# Command line entry point for running the media class and glitching media

import argparse, random, sys
from media import media

# default header length in lines, messing with the headers will just break the media
DEFAULT_HEADER_LENGTH = 15

# glitch operations used when none are given on the command line
DEFAULT_OPERATIONS = [("corrupt", 5000, 8), ("swap", 820, 3)]

# named groups of operations, these settings have gotten good results
PRESETS = {
    "recommended": [("swap", 200, 50), ("swap", 100, 3), ("corrupt", 200, 30),
                    ("corrupt", 400, 3), ("swap", 40, 3)],
    "classic": [("swap", 200, 50), ("swap", 100, 3), ("corrupt", 200, 30),
                ("corrupt", 400, 3), ("swap", 56, 4), ("swap", 300, 1)],
}

# argparse type for INTERVAL,FLAVOUR values
def interval_flavour(text):
    try:
        interval, flavour = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected INTERVAL,FLAVOUR (two integers), got '%s'" % text)
    if interval < 0:
        raise argparse.ArgumentTypeError("INTERVAL must not be negative")
    return interval, flavour

# argparse action that records operations in the order they appear on the command line
class AddOperation(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        operations = getattr(namespace, "operations", None) or []
        if self.dest == "preset":
            operations.extend(PRESETS[values])
        else:
            operations.append((self.dest,) + values)
        namespace.operations = operations

def build_parser():
    parser = argparse.ArgumentParser(
        description="Glitch a media file by swapping and corrupting lines of its raw data.",
        epilog="Operations run in the order given. With none given, the defaults are: "
               + " ".join("--%s %d,%d" % op for op in DEFAULT_OPERATIONS))
    parser.add_argument("input_file", help="file to glitch")
    parser.add_argument("output_file", help="where to write the glitched file (overwritten)")
    parser.add_argument("--swap", metavar="INTERVAL,FLAVOUR", type=interval_flavour,
                        action=AddOperation, help="add a random swap operation (repeatable)")
    parser.add_argument("--corrupt", metavar="INTERVAL,FLAVOUR", type=interval_flavour,
                        action=AddOperation, help="add a corrupt operation (repeatable)")
    parser.add_argument("--preset", choices=sorted(PRESETS), action=AddOperation,
                        help="add a named group of operations")
    parser.add_argument("--header-length", type=int, default=DEFAULT_HEADER_LENGTH, metavar="LINES",
                        help="lines at the start of the file left untouched; "
                             "15 is good for video, 0 may be fine for images (default: %(default)s)")
    parser.add_argument("--seed", type=int, help="random seed, for reproducible output")
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print the file names")
    return parser

def main(argv=None):
    parser = build_parser()
    parser.set_defaults(operations=None)
    args = parser.parse_args(argv)
    if args.header_length < 0:
        parser.error("--header-length must not be negative")
    if args.input_file == args.output_file:
        parser.error("input and output files must be different")
    operations = args.operations or DEFAULT_OPERATIONS
    if args.seed is not None:
        random.seed(args.seed)

    if not args.quiet:
        print("Input File: ", args.input_file)
        print("Output File: ", args.output_file)

    # latin-1 maps bytes 1:1 to characters, so binary media survives the text round trip
    try:
        with open(args.input_file, "r", encoding="latin-1", newline="") as file:
            lines = file.readlines()
    except OSError as error:
        parser.exit(1, "error: %s\n" % error)
    if len(lines) < args.header_length:
        parser.exit(1, "error: file has only %d lines, fewer than --header-length\n" % len(lines))

    with open(args.output_file, "w", encoding="latin-1", newline="") as new_file:
        media_to_work_on = media(lines, new_file, args.header_length)
        for kind, interval, flavour in operations:
            if kind == "swap":
                media_to_work_on.glitch_random_swap(interval, flavour)
            else:
                media_to_work_on.glitch_corrupt(interval, flavour)
        media_to_work_on.print_to_new_file()

if __name__ == "__main__":
    main()
