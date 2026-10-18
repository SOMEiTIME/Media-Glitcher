#!/usr/bin/env bash
# Print one field of the JSON object on stdin, e.g. `json-field.sh tool_input.command`.
# Strings print raw, other values as JSON (true, 42), missing fields as nothing.
# Uses jq, python3 or node, whichever is installed first. Exits 1 if none is
# installed or the JSON doesn't parse, so callers can fail open.

path="$1"

if command -v jq >/dev/null 2>&1; then
  jq -er --arg p "$path" 'getpath($p | split(".")) // empty | if type == "string" then . else tojson end'
  rc=$?
  # jq -e exits 1 for a missing/null field and 4 for no input; both just mean "no value".
  [ $rc -eq 1 ] || [ $rc -eq 4 ] && exit 0
  exit $rc
elif command -v python3 >/dev/null 2>&1; then
  python3 -c '
import json, sys
value = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    value = value.get(key) if isinstance(value, dict) else None
if value is not None:
    sys.stdout.write(value if isinstance(value, str) else json.dumps(value))
' "$path"
elif command -v node >/dev/null 2>&1; then
  node -e '
let input = "";
process.stdin.on("data", c => input += c).on("end", () => {
  let value = JSON.parse(input);
  for (const key of process.argv[1].split(".")) value = value && typeof value === "object" ? value[key] : undefined;
  if (value !== undefined && value !== null) process.stdout.write(typeof value === "string" ? value : JSON.stringify(value));
});
' "$path"
else
  exit 1
fi
