#!/usr/bin/env bash
#
# Render the CV to both CV.html and CV_Sippel.pdf.
#
#   CV.html        - produced by Quarto from CV.qmd
#   CV_Sippel.pdf  - printed from CV.html by make_pdf.R (headless Chrome),
#                    wired up as a post-render hook in _quarto.yml, so it
#                    matches the web page exactly.
#
# Usage:  ./render.sh
#
set -euo pipefail

# Run from the directory this script lives in, regardless of where it's called.
cd "$(dirname "$0")"

echo "Rendering CV.qmd -> CV.html + CV_Sippel.pdf ..."

# pagedown::chrome_print occasionally fails on a cold Chrome start; retry once.
for attempt in 1 2; do
  if quarto render CV.qmd; then
    echo "✔ Done:"
    echo "    $(pwd)/CV.html"
    echo "    $(pwd)/CV_Sippel.pdf"
    exit 0
  fi
  echo "Render attempt ${attempt} failed." >&2
  if [ "${attempt}" -lt 2 ]; then
    echo "Retrying in 2s..." >&2
    sleep 2
  fi
done

echo "✖ Render failed after 2 attempts." >&2
exit 1
