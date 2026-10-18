#!/usr/bin/env bash
# PreToolUse hook for Bash. Reads the hook JSON on stdin and exits 2 (block,
# reason on stderr) for commands that are hard to undo or leak secrets:
#   - recursive rm of /, ~, $VARS, .., the repo root, .git, or anything outside the repo
#   - force pushes, pushes to main/master, git reset --hard to a remote branch,
#     deleting main/master
#   - commands that name .env files, keys or credential files
#   - piping a download into a shell (curl ... | sh)
# Pattern matching is best-effort: it catches the forms Claude usually writes,
# not every possible spelling. Fails open (exit 0 with a warning) if the input
# can't be parsed, so a broken hook never blocks every command.
# Written for bash 3.2, which is what macOS ships.

set -f # words from the command are data; never glob-expand them
hook_dir="$(cd "$(dirname "$0")" && pwd)"
input="$(cat)"

if ! command="$(printf '%s' "$input" | "$hook_dir/json-field.sh" tool_input.command)"; then
  echo "block-dangerous.sh: couldn't parse hook input (needs jq, python3 or node); allowing command unchecked" >&2
  exit 0
fi
[ -z "$command" ] && exit 0

cwd="$(printf '%s' "$input" | "$hook_dir/json-field.sh" cwd)"
[ -d "$cwd" ] || cwd="$PWD"
repo_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$repo_root" ] || repo_root="$(cd "${CLAUDE_PROJECT_DIR:-$cwd}" && pwd -P)"

block() {
  echo "Blocked by .claude/hooks/block-dangerous.sh: $1. If this really is needed, ask the user to run it themselves." >&2
  exit 2
}

# --- whole-command checks ------------------------------------------------------

# Download piped or substituted into an interpreter.
pipe_to_shell='(curl|wget)[^;&]*\|[[:space:]]*(sudo[[:space:]]+)?(env[[:space:]]+)?(sh|bash|zsh|dash|ksh|fish|python[0-9.]*|perl|ruby|node)([[:space:]]|$)'
shell_of_download='(^|[^A-Za-z0-9_])(sh|bash|zsh|dash|ksh|source|\.)[[:space:]]+(-[A-Za-z]+[[:space:]]+)*.?(<\(|\$\()[[:space:]]*(curl|wget)'
if [[ $command =~ $pipe_to_shell ]] || [[ $command =~ $shell_of_download ]]; then
  block "piping a download into a shell runs unreviewed code"
fi

# Secret files, named anywhere in the command (cat, cp, grep, git add, echo >> ...).
before='(^|[^A-Za-z0-9_.-])'
after='($|[^A-Za-z0-9_.-])'
secret_patterns=(
  "${before}\.env(\.[A-Za-z0-9_.-]+)?${after}"
  "[A-Za-z0-9_-]\.(pem|key)($|[[:space:]\"'])"
  "${before}id_(rsa|dsa|ecdsa|ed25519)"
  "${before}\.(netrc|git-credentials|pypirc)${after}"
  "\.aws/credentials"
  "${before}credentials\.json${after}"
)
for pattern in "${secret_patterns[@]}"; do
  if [[ $command =~ $pattern ]]; then
    block "the command names a secrets file (${BASH_REMATCH[0]# }); .env files, keys and credentials stay unread"
  fi
done

# --- per-command checks --------------------------------------------------------

# Prints the reason if rm -r on path $1 isn't safe, nothing if it is.
unsafe_rm_target() {
  local target="$1" path parent
  case "$target" in
    "~"*) echo "it targets your home directory"; return ;;
    "\$"*) echo "it starts with a variable ($target) whose value can't be checked; use a literal path"; return ;;
    ..|../*|*/..|*/../*) echo "it uses .. to leave the current directory"; return ;;
    .|./|"*") echo "it deletes the whole working directory"; return ;;
  esac
  case "$target" in
    /*) path="$target" ;;
    *) path="$cwd/$target" ;;
  esac
  while [ "${path%/}" != "$path" ] && [ "$path" != "/" ]; do path="${path%/}"; done
  path="${path%/.}"
  # Resolve symlinks in the parent (macOS /var -> /private/var) to compare with git's path.
  parent="$(cd "$(dirname "$path")" 2>/dev/null && pwd -P)" && path="${parent%/}/$(basename "$path")"

  if [ "$path" = "$repo_root" ] || [ "$path" = "$repo_root/.git" ]; then
    echo "it deletes the repo or its .git directory"; return
  fi
  case "$path" in
    "$repo_root"/*|/tmp/*|/private/tmp/*|/var/folders/*|/private/var/folders/*) return ;;
  esac
  if [ -n "$TMPDIR" ]; then
    case "$path" in "${TMPDIR%/}"/*) return ;; esac
  fi
  echo "$target is outside the repo ($repo_root)"
}

check_rm() {
  local recursive="" args_done="" word reason
  local -a targets=()
  for word in "$@"; do
    if [ -z "$args_done" ]; then
      case "$word" in
        --) args_done=1; continue ;;
        --recursive) recursive=1; continue ;;
        --*) continue ;;
        -*) [[ $word == *[rR]* ]] && recursive=1; continue ;;
      esac
    fi
    targets+=("$word")
  done
  [ -n "$recursive" ] || return
  for word in ${targets[@]+"${targets[@]}"}; do
    reason="$(unsafe_rm_target "$word")"
    [ -n "$reason" ] && block "recursive rm refused: $reason"
  done
}

is_main() { [ "$1" = main ] || [ "$1" = master ]; }

check_git() {
  # Skip git's global options (-C <dir>, -c <key=value>, --no-pager, ...).
  while [ $# -gt 0 ]; do
    case "$1" in
      -C|-c) shift 2 ;;
      -*) shift ;;
      *) break ;;
    esac
  done
  local subcommand="$1" word
  shift

  case "$subcommand" in
    push)
      local -a positional=()
      while [ $# -gt 0 ]; do
        word="$1"; shift
        case "$word" in
          --force*|--force-with-lease*|--force-if-includes) block "force pushes are not allowed" ;;
          --mirror|--all) block "git push $word would push main/master too" ;;
          -o|--push-option|--repo|--receive-pack|--exec) shift ;;
          --*) ;;
          -*) [[ $word == *f* ]] && block "force pushes are not allowed" ;;
          +*) block "a +refspec is a force push" ;;
          *) positional+=("$word") ;;
        esac
      done
      # positional[0] is the remote; the rest are refspecs (src:dst or just a branch).
      local i dst
      for ((i = 1; i < ${#positional[@]}; i++)); do
        dst="${positional[$i]##*:}"
        dst="${dst#refs/heads/}"
        is_main "$dst" && block "pushing to $dst is not allowed; push a branch and open a PR"
      done
      if [ ${#positional[@]} -le 1 ]; then
        local current
        current="$(git -C "$cwd" branch --show-current 2>/dev/null)"
        is_main "$current" && block "a bare git push from $current would push to $current; push a branch and open a PR"
      fi
      ;;
    branch)
      local deleting="" names=""
      for word in "$@"; do
        case "$word" in
          --delete|-d|-D|-df|-fd|-Df|-fD) deleting=1 ;;
          -*) ;;
          *) names="$names $word" ;;
        esac
      done
      if [ -n "$deleting" ]; then
        for word in $names; do
          is_main "$word" && block "deleting the $word branch is not allowed"
        done
      fi
      ;;
    reset)
      local hard="" remote_target=""
      for word in "$@"; do
        case "$word" in
          --hard) hard=1 ;;
          origin/*|upstream/*|*@{u}*|*@{upstream}*) remote_target="$word" ;;
        esac
      done
      [ -n "$hard" ] && [ -n "$remote_target" ] &&
        block "git reset --hard $remote_target throws away local commits and changes"
      ;;
  esac
}

# Split into simple commands at ; & | && || newlines and $( ( ) `, then check each.
segments="$(printf '%s\n' "$command" | awk '{ gsub(/&&|\|\||[;&|`()]/, "\n"); print }')"
while IFS= read -r segment; do
  read -ra words <<<"$segment"
  [ ${#words[@]} -gt 0 ] || continue
  # Strip quotes from each word (best-effort; this is not a full shell parser).
  for i in "${!words[@]}"; do
    words[$i]="${words[$i]//\"/}"
    words[$i]="${words[$i]//\'/}"
  done
  # Skip VAR=value prefixes and wrapper commands (sudo, env, xargs, ...) and their flags.
  start=0
  while [ $start -lt ${#words[@]} ]; do
    case "${words[$start]}" in
      sudo|env|command|nohup|time|exec|xargs|nice) start=$((start + 1))
        while [ $start -lt ${#words[@]} ] && [[ ${words[$start]} == -* ]]; do start=$((start + 1)); done ;;
      [A-Za-z_]*=*) start=$((start + 1)) ;;
      *) break ;;
    esac
  done
  [ $start -lt ${#words[@]} ] || continue
  program="${words[$start]##*/}"
  args=("${words[@]:$((start + 1))}")
  case "$program" in
    rm) check_rm ${args[@]+"${args[@]}"} ;;
    git) check_git ${args[@]+"${args[@]}"} ;;
  esac
done <<<"$segments"

exit 0
