#!/usr/bin/env bash
# Verify for Media-Glitcher: the unittest suite (stdlib only, no install step).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests
