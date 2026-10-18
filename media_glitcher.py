#!/usr/bin/env python3

# Command line entry point for glitching media

import argparse, os
import engine, presets

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
            op = {"type": op_type, **{name: kind(part) for (name, kind, _), part in zip(params, parts)}}
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

# first argument that isn't None
def first_set(*values):
    return next((v for v in values if v is not None), None)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Glitch a media file by swapping and corrupting its raw data, by lines or by bytes.",
        epilog="Operations run in the order given. With none given, the '%s' preset is used." % DEFAULT_PRESET)
    parser.add_argument("input_file", nargs="?", help="file to glitch")
    parser.add_argument("output_file", nargs="?", help="where to write the glitched file (overwritten)")
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
    header_length = first_set(args.header_length, settings.get("header_length"), engine.DEFAULT_HEADER_LENGTH)
    header_bytes = first_set(args.header_bytes, settings.get("header_bytes"), engine.DEFAULT_HEADER_BYTES)
    seed = first_set(args.seed, settings.get("seed"))
    target = first_set(args.target, settings.get("target"), engine.DEFAULT_TARGET)
    if header_length < 0:
        parser.error("--header-length must not be negative")
    if header_bytes < 0:
        parser.error("--header-bytes must not be negative")

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
        # only store the header settings the operations actually use
        uses_lines = any(engine.is_line_operation(op) for op in operations)
        uses_bytes = any(not engine.is_line_operation(op) for op in operations)
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
    try:
        data = engine.glitch(data, operations, header_length, header_bytes, seed, target)
    except engine.GlitchError as error:
        parser.exit(1, "error: %s\n" % error)
    with open(args.output_file, "wb") as file:
        file.write(data)

if __name__ == "__main__":
    main()
