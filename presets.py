#!/usr/bin/env python3

import json, os
import engine

# Presets are JSON files describing a whole glitch run:
#
#   {
#     "description": "free text, optional",
#     "header_length": 15,          optional, lines left alone by line operations
#     "header_bytes": 1024,         optional, bytes left alone by byte operations
#     "seed": 42,                   optional, makes the output reproducible
#     "operations": [               run in order, see engine.OPERATIONS for every type
#       {"type": "swap", "interval": 200, "flavour": 50},
#       {"type": "byte-swap", "size": 64, "every": 5000}
#     ]
#   }
#
# This module has no dependency on the CLI so other programs and tests can use it.

PRESET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
KNOWN_FIELDS = ("description", "header_length", "header_bytes", "seed", "operations")

class PresetError(ValueError):
    pass

# True for real integers; bool is a subclass of int, but true/false aren't valid numbers here
def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)

# True for numbers a float parameter accepts
def is_number(value):
    return is_int(value) or isinstance(value, float)

#
# Checks one operation dict and returns a copy with its keys in the standard
# order. Raises PresetError if the type is unknown or a parameter is wrong
#
def check_operation(op):
    if not isinstance(op, dict) or op.get("type") not in engine.OPERATIONS:
        raise PresetError("type must be one of %s" % ", ".join(engine.OPERATIONS))
    params = engine.OPERATIONS[op["type"]]
    names = [name for name, _, _ in params]
    if set(op) != {"type", *names}:
        raise PresetError("%s needs exactly %s" % (op["type"], ", ".join(names)))
    for name, kind, minimum in params:
        if not (is_int(op[name]) if kind is int else is_number(op[name])):
            raise PresetError("%s: %s must be %s" % (op["type"], name, "an integer" if kind is int else "a number"))
        if minimum is not None and op[name] < minimum:
            raise PresetError("%s: %s must be at least %s" % (op["type"], name, minimum))
    return {"type": op["type"], **{name: op[name] for name in names}}

#
# Checks a preset dict and returns it with its operations normalised.
# Raises PresetError on anything malformed
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
        try:
            checked.append(check_operation(op))
        except PresetError as error:
            raise PresetError("operation %d: %s" % (number, error))
    for key in ("header_length", "header_bytes", "seed"):
        if data.get(key) is not None and not is_int(data[key]):
            raise PresetError("'%s' must be an integer" % key)
    for key in ("header_length", "header_bytes"):
        if (data.get(key) or 0) < 0:
            raise PresetError("'%s' must not be negative" % key)
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

#
# Writes a preset file and returns its path. Refuses to replace an existing
# preset unless overwrite is set
#
def save(name_or_path, operations, header_length=None, seed=None, description="", overwrite=False,
         header_bytes=None):
    data = {"description": description}
    for key, value in (("header_length", header_length), ("header_bytes", header_bytes), ("seed", seed)):
        if value is not None:
            data[key] = value
    data["operations"] = list(operations)
    data = validate(data)
    path = resolve(name_or_path)
    if os.path.exists(path) and not overwrite:
        raise PresetError("preset %s already exists" % path)
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
