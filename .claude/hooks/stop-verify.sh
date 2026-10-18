#!/usr/bin/env bash
# Stop hook. Runs the repo's .claude/verify.sh when Claude finishes a turn and,
# if it fails, exits 2 with the tail of its output so Claude keeps fixing.
# - Stop fires at the end of every turn, so verify only runs when the branch
#   has work on it (uncommitted changes, or commits not on the default branch)
#   and that work changed since the last passing run.
# - If this stop was already forced by a Stop hook (stop_hook_active), it lets
#   Claude stop: one forced retry per turn, then it's back to the user.
# - verify.sh is killed after VERIFY_TIMEOUT seconds (default 540, under the
#   600s hook timeout in settings.json) and the timeout counts as a failure.
# Fails open: any problem with the hook itself allows the stop.
# Written for bash 3.2, which is what macOS ships.

hook_dir="$(cd "$(dirname "$0")" && pwd)"
input="$(cat)"

if ! active="$(printf '%s' "$input" | "$hook_dir/json-field.sh" stop_hook_active)"; then
  echo "stop-verify.sh: couldn't parse hook input (needs jq, python3 or node); skipping verify" >&2
  exit 0
fi
[ "$active" = true ] && exit 0

cwd="$(printf '%s' "$input" | "$hook_dir/json-field.sh" cwd)"
[ -d "$cwd" ] || cwd="${CLAUDE_PROJECT_DIR:-$PWD}"
repo_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)" || exit 0
verify="$repo_root/.claude/verify.sh"
[ -x "$verify" ] || exit 0
cd "$repo_root" || exit 0

# Is there any work on this branch? Compare against origin's default branch.
default_ref="$(git symbolic-ref -q --short refs/remotes/origin/HEAD)"
for candidate in origin/main origin/master; do
  [ -n "$default_ref" ] && break
  git rev-parse -q --verify "$candidate" >/dev/null && default_ref="$candidate"
done
dirty="$(git status --porcelain)"
if [ -z "$dirty" ] && [ -n "$default_ref" ] && git merge-base --is-ancestor HEAD "$default_ref"; then
  exit 0
fi

# Fingerprint of the working tree: HEAD, uncommitted diff, untracked file contents.
fingerprint() {
  {
    git rev-parse HEAD
    git diff HEAD --binary
    git ls-files -o --exclude-standard -z | xargs -0 git hash-object -- 2>/dev/null
  } | git hash-object --stdin
}
stamp="$(git rev-parse --git-path claude-verify-passed)"
[ -f "$stamp" ] && [ "$(cat "$stamp")" = "$(fingerprint)" ] && exit 0

# Run verify in its own process group so a timeout kills everything it started.
log="$(mktemp -t claude-verify.XXXXXX)"
trap 'rm -f "$log"' EXIT
timeout_secs="${VERIFY_TIMEOUT:-540}"
set -m
"$verify" >"$log" 2>&1 </dev/null &
verify_pid=$!
(sleep "$timeout_secs" && kill -TERM -- -"$verify_pid" 2>/dev/null) &
watchdog_pid=$!
wait "$verify_pid"
status=$?
kill -TERM -- -"$watchdog_pid" 2>/dev/null
set +m

if [ $status -eq 0 ]; then
  fingerprint >"$stamp"
  exit 0
fi

if [ $status -eq 143 ]; then
  summary="timed out after ${timeout_secs}s (a hung test or dev server?)"
else
  summary="failed (exit $status)"
fi
{
  echo ".claude/verify.sh $summary. The work isn't done until it passes; fix it, or tell the user why it can't pass. Last 40 lines:"
  tail -n 40 "$log"
} >&2
exit 2
