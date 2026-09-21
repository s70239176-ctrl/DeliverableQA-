#!/usr/bin/env bash
# Minimal StudioNet deploy helper. Runs the static preflight first, then deploys with the GenLayer CLI.
#   npm install -g genlayer   (once)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/preflight.py
genlayer network set studionet
genlayer deploy --contract contracts/deliverable_qa.py
