#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKING_DIR="${ROOT_DIR}/data/working"
OUTPUT_DIR="${ROOT_DIR}/data/output"
INPUT_DIR="${ROOT_DIR}/data/input"

REMOVE_INPUT=false

if [[ "${1:-}" == "--all" ]]; then
  REMOVE_INPUT=true
fi

clean_dir() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    return
  fi

  find "$dir" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +
}

echo "Cleaning generated data..."
clean_dir "$WORKING_DIR"
clean_dir "$OUTPUT_DIR"

if [[ "$REMOVE_INPUT" == true ]]; then
  echo "Also cleaning data/input because --all was provided..."
  clean_dir "$INPUT_DIR"
fi

echo "Done. Fresh state ready."
