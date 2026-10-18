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

# Presets live in one subfolder per group under presets/:
#   builtin  shipped with the tool
#   user     saved with --save-preset (bare names are saved here)
#   test     seeded presets used by the golden test cases
# A bare name is looked up in this order, so a user preset can shadow a builtin one.
# 'group/name' picks one explicitly.
GROUPS = ("user", "builtin", "test")
SAVE_GROUP = "user"
OPERATION_TYPES = ("swap", "corrupt")
KNOWN_FIELDS = ("description", "header_length", "seed", "operations")

class PresetError(ValueError):
    pass

#
# Checks a preset dict and returns it with operations normalised to
# (type, interval, flavour) tuples. Raises PresetError on anything malformed
#
def validate(data):
    if not isinstance(data, dict):
        raise PresetError("preset must be a JSON object")
    unknown = set(data) - set(KNOWN_FIELDS)
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
            if not isinstance(op[key], int) or isinstance(op[key], bool):
                raise PresetError("operation %d: %s must be an integer" % (number, key))
        if op["interval"] < 0:
            raise PresetError("operation %d: interval must not be negative" % number)
        checked.append((op["type"], op["interval"], op["flavour"]))
    for key in ("header_length", "seed"):
        value = data.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise PresetError("'%s' must be an integer" % key)
    if data.get("header_length") is not None and data["header_length"] < 0:
        raise PresetError("'header_length' must not be negative")
    if not isinstance(data.get("description", ""), str):
        raise PresetError("'description' must be a string")
    return dict(data, operations=checked)

#
# Turns a preset name or path into a file path. 'group/name' and bare names are
# looked up in the presets folder, anything else with a path separator or .json
# is used as is. With for_save, a bare name always goes to the user group
#
def resolve(name_or_path, for_save=False):
    group, _, name = name_or_path.partition("/")
    if group in GROUPS and name and "/" not in name:
        return os.path.join(PRESET_DIR, group, name + ".json")
    if "/" in name_or_path or os.sep in name_or_path or name_or_path.endswith(".json"):
        return name_or_path
    if not for_save:
        for group in GROUPS:
            candidate = os.path.join(PRESET_DIR, group, name_or_path + ".json")
            if os.path.exists(candidate):
                return candidate
    return os.path.join(PRESET_DIR, SAVE_GROUP, name_or_path + ".json")

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
    path = resolve(name_or_path, for_save=True)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")
    return path

# Presets in each group as (group, name, description), groups in lookup order
def list_presets():
    found = []
    for group in GROUPS:
        folder = os.path.join(PRESET_DIR, group)
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if filename.endswith(".json"):
                name = filename[:-5]
                try:
                    found.append((group, name, load(group + "/" + name).get("description", "")))
                except PresetError as error:
                    found.append((group, name, "(invalid: %s)" % error))
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
