#!/usr/bin/env bash
# Ensure the geest plugin from this checkout is symlinked into the QGIS
# profile's python/plugins folder so the launcher scripts always run the
# working-tree code.
#
# Usage: ensure_plugin_link.sh <profile> <qgis-data-root> [more roots...]
#   profile          e.g. GEOE3
#   qgis-data-root   e.g. QGIS4 (QGIS 4.x) or QGIS3 (QGIS 3.x)
#
# The first root is always provisioned (created if needed); additional roots
# are only linked when they already exist. An existing real directory (a
# copy-installed plugin) is never touched — we warn instead of replacing it.
set -euo pipefail

PROFILE="$1"
shift

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_SRC="$REPO_DIR/geest"

first=1
for root in "$@"; do
  base="$HOME/.local/share/QGIS/$root"
  if [ "$first" -ne 1 ] && [ ! -d "$base" ]; then
    continue
  fi
  first=0
  plugins_dir="$base/profiles/$PROFILE/python/plugins"
  mkdir -p "$plugins_dir"
  link="$plugins_dir/geest"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "⚠️  $link exists and is not a symlink — leaving it alone." >&2
    echo "    Remove it manually to use the working-tree plugin." >&2
    continue
  fi
  if [ "$(readlink "$link" 2>/dev/null || true)" != "$PLUGIN_SRC" ]; then
    ln -sfn "$PLUGIN_SRC" "$link"
    echo "🔗 linked $link -> $PLUGIN_SRC"
  fi
done
