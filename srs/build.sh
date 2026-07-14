#!/usr/bin/env bash
# Build the GeoE3 SRS deliverables: docx + pdf + per-diagram SVGs.
# Diagrams via plantuml; the document is written directly into the Kartoza
# Word template with python-docx (no pandoc).
set -euo pipefail
cd "$(dirname "$0")"

TEMPLATE="../srs-gitignore/Kartoza_BrandTemplates_v1.0.0/templates/Kartoza_Document_Template.docx"
NIX="nix --extra-experimental-features nix-command --extra-experimental-features flakes"

# Brand fonts must be visible to fontconfig for plantuml (diagram text) and
# LibreOffice (PDF conversion) — otherwise everything silently falls back to
# DejaVu and bold/italic faces are lost. Build a throwaway fonts.conf that
# points straight at the nix store.
FONT_PKGS="$($NIX build --no-link --print-out-paths nixpkgs#lato nixpkgs#dejavu_fonts)"
JBM="$($NIX build --no-link --print-out-paths nixpkgs#jetbrains-mono)"
FCDIR="$(mktemp -d)"
trap 'rm -rf "$FCDIR"' EXIT
# JetBrains Mono ships WOFF2/variable faces that LibreOffice cannot embed —
# stage only the four static TTFs it needs.
mkdir -p "$FCDIR/fonts"
$NIX shell nixpkgs#jetbrains-mono --command bash -c \
  "cp '$JBM'/share/fonts/truetype/JetBrainsMono-{Regular,Bold,Italic,BoldItalic}.ttf '$FCDIR/fonts/'"
{
  echo '<?xml version="1.0"?>'
  echo '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
  echo '<fontconfig>'
  echo "  <dir>$FCDIR/fonts</dir>"
  for p in $FONT_PKGS; do echo "  <dir>$p/share/fonts</dir>"; done
  echo "  <cachedir>$FCDIR/cache</cachedir>"
  echo '</fontconfig>'
} > "$FCDIR/fonts.conf"
export FONTCONFIG_FILE="$FCDIR/fonts.conf"

echo "── 0. generate model catalogue chapter from model.json"
LATO_DIR="$($NIX build --no-link --print-out-paths nixpkgs#lato)/share/fonts/lato"
$NIX shell --impure --expr 'with import <nixpkgs> {}; python3.withPackages (ps: [ ps.pillow ])' \
  --command env PYTHONPATH= LATO_DIR="$LATO_DIR" python3 scripts/gen_model_catalogue.py \
  ../geest/resources/model.json .

echo "── 1. diagrams (SVG + PNG)"
(cd diagrams && $NIX shell nixpkgs#plantuml --command bash -c \
  'plantuml -tsvg fig*.puml && plantuml -tpng -Sdpi=220 fig*.puml')

echo "── 2. write docx directly into the Kartoza template"
mkdir -p dist
$NIX shell --impure --expr 'with import <nixpkgs> {}; python3.withPackages (ps: [ ps.python-docx ps.pillow ])' \
  --command env PYTHONPATH= python3 scripts/build_docx.py "$TEMPLATE" GeoE3_SRS.md assets/cover.png \
  dist/GeoE3_SRS_v1.0.0.docx

echo "── 3. PDF"
soffice --headless "-env:UserInstallation=file://$FCDIR/lo-profile" \
  --convert-to pdf dist/GeoE3_SRS_v1.0.0.docx --outdir dist >/dev/null 2>&1

echo "── done:"
ls -la dist/
