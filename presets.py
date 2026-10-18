#!/usr/bin/env python3

import json, os

# Presets are JSON files describing a whole glitch run:
#
#   {
#     "description": "free text, optional",
#     "header_length": 15,          optional
#     "seed": 42,                   optional, makes the output reproducible
#     "operations": [               run in order
#       {"type": "swap", "interval": 200, "flavour": 50},
#       {"type": "corrupt", "interval": 200, "flavour": 30}
#     ]
#   }
#
# This module has no dependency on the CLI so other programs and tests can use it.

PRESET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
OPERATION_TYPES = ("swap", "corrupt")
KNOWN_FIELDS = ("description", "header_length", "seed", "operations")

class PresetError(ValueError):
    pass

# True for real integers; bool is a subclass of int, but true/false aren't valid numbers here
def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)

#
# Checks a preset dict and returns it with operations normalised to
# (type, interval, flavour) tuples. Raises PresetError on anything malformed
#
def validate(data):
    if not isinstance(data, dict):
        raise PresetError("preset must be a JSON object")
    unknown = set(data).difference(KNOWN_FIELDS)
    if unknown:
        raise PresetError("unknown field(s): " + ", ".join(sorted(unknown)))
    operations = data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise PresetError("'operations' must be a non-empty list")
    checked = []
    for number, op in enumerate(operations, 1):
        if not isinstance(op, dict) or set(op) != {"type", "interval", "flavour"}:
            raise PresetError("operation %d needs exactly type, interval and flavour" % number)
        if op["type"] not in OPERATION_TYPES:
            raise PresetError("operation %d: type must be one of %s" % (number, ", ".join(OPERATION_TYPES)))
        for key in ("interval", "flavour"):
            if not is_int(op[key]):
                raise PresetError("operation %d: %s must be an integer" % (number, key))
        if op["interval"] < 0:
            raise PresetError("operation %d: interval must not be negative" % number)
        checked.append((op["type"], op["interval"], op["flavour"]))
    for key in ("header_length", "seed"):
        if data.get(key) is not None and not is_int(data[key]):
            raise PresetError("'%s' must be an integer" % key)
    if (data.get("header_length") or 0) < 0:
        raise PresetError("'header_length' must not be negative")
    if not isinstance(data.get("description", ""), str):
        raise PresetError("'description' must be a string")
    return dict(data, operations=checked)

#
# Turns a preset name or path into a file path. A bare name is looked up in
# the presets folder, anything with a path separator or .json is used as is
#
def resolve(name_or_path):
    if os.sep in name_or_path or name_or_path.endswith(".json"):
        return name_or_path
    return os.path.join(PRESET_DIR, name_or_path + ".json")

def load(name_or_path):
    path = resolve(name_or_path)
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except OSError as error:
        raise PresetError("cannot read preset: %s" % error)
    except json.JSONDecodeError as error:
        raise PresetError("%s is not valid JSON: %s" % (path, error))
    try:
        return validate(data)
    except PresetError as error:
        raise PresetError("%s: %s" % (path, error))

def save(name_or_path, operations, header_length=None, seed=None, description=""):
    data = {"description": description}
    if header_length is not None:
        data["header_length"] = header_length
    if seed is not None:
        data["seed"] = seed
    data["operations"] = [{"type": t, "interval": i, "flavour": f} for t, i, f in operations]
    validate(data)
    path = resolve(name_or_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # same layout as the bundled presets: one operation per line, easy to edit by hand
    settings = ",\n".join("  %s: %s" % (json.dumps(k), json.dumps(v)) for k, v in data.items() if k != "operations")
    operations = ",\n".join("    " + json.dumps(op) for op in data["operations"])
    with open(path, "w", encoding="utf-8") as file:
        file.write('{\n%s,\n  "operations": [\n%s\n  ]\n}\n' % (settings, operations))
    return path

# (name, description) for every preset in the presets folder
def list_presets():
    found = []
    if os.path.isdir(PRESET_DIR):
        for filename in sorted(os.listdir(PRESET_DIR)):
            if filename.endswith(".json"):
                name = os.path.splitext(filename)[0]
                try:
                    found.append((name, load(name).get("description", "")))
                except PresetError as error:
                    found.append((name, "(invalid: %s)" % error))
    return found

#
# Runs the operations on a media object, in order
#
def apply(media_object, operations):
    for kind, interval, flavour in operations:
        if kind == "swap":
            media_object.glitch_random_swap(interval, flavour)
        else:
            media_object.glitch_corrupt(interval, flavour)
