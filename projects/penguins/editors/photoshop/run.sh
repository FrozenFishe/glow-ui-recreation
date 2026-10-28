#!/bin/sh
# Rebuild the Photoshop kit, the exact layers and penguins_ps.psd, then score the renders.
set -e
cd "$(dirname "$0")/../../../.."
P=tools/.venv/bin/python; K=~/Downloads/penguins_kit; D=~/Downloads/penguins_photoshop
$P tools/recreate.py penguins kit photoshop --out $K >/dev/null
rm -rf $K/exact; $P tools/recreate.py penguins exact --out $K/exact >/dev/null
cp projects/penguins/build/pill.png $K/hero_outline_button_backdrop.png
osascript -e 'tell application "Adobe Photoshop 2026" to do javascript (read POSIX file "'"$PWD"'/projects/penguins/editors/photoshop/build.jsx")' >/dev/null
$P tools/recreate.py penguins bench "Photoshop=$D/penguins_ps.png" "Photoshop vectors only=$D/penguins_ps_vectors_only.png" \
  "Photoshop max=$D/penguins_ps_max.png" "Photoshop exact=$D/penguins_ps_exact.png" 2>&1 | grep "^| Photo"
