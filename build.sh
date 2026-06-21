#!/usr/bin/env bash
# build.sh — assemble the ARD from source catalogues
# Clones each catalogue repo, then compiles the agent-resources manifest.
# On Cloud Run: runs at container build time (Dockerfile CMD).
# Locally: run after cloning this repo to bootstrap.
#
# Prerequisites: both source repos must be public on GitHub before running.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 0. Prerequisite check ─────────────────────────────────────────────────────
check_repo_public() {
  local repo_url="$1"
  if ! git ls-remote "$repo_url" HEAD &>/dev/null; then
    echo "ERROR: Cannot access $repo_url"
    echo "       Make sure both a2knowledge and a2ui are public on GitHub before running build.sh"
    exit 1
  fi
}

echo "⏳ Checking source repos are accessible..."
check_repo_public "https://github.com/curtiskrygier/a2knowledge.git"
check_repo_public "https://github.com/curtiskrygier/a2ui.git"

# ── 1. Clone / refresh source catalogues ──────────────────────────────────────
clone_or_pull() {
  local repo="$1" dest="$2"
  if [ -d "$dest/.git" ]; then
    echo "↻  refreshing $dest"
    git -C "$dest" pull --ff-only
  else
    echo "⬇  cloning $repo → $dest"
    git clone --depth 1 "$repo" "$dest"
  fi
}

# a2knowledge  (structured competency knowledge — schemas + curricula)
clone_or_pull \
  "https://github.com/curtiskrygier/a2knowledge.git" \
  "$DIR/sources/a2knowledge"

# a2ui  (rendering vocabulary — atom definitions + payloads)
clone_or_pull \
  "https://github.com/curtiskrygier/a2ui.git" \
  "$DIR/sources/a2ui"

# ── 2. Compile agent-resources manifest ───────────────────────────────────────
echo "⚙  compiling .well-known/agent-resources.json"
python3 "$DIR/compile.py" \
  --registry "$DIR/sources/a2knowledge/schemas/registry.yaml" \
  --output "$DIR/.well-known/agent-resources.json"

echo "✓  ARD build complete"
