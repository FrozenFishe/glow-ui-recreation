#!/usr/bin/env bash
# One-time setup for the recreation tools (macOS). Installs potrace, a Python env and Real-ESRGAN.
set -euo pipefail
cd "$(dirname "$0")"
command -v potrace >/dev/null || brew install potrace
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
if [ ! -x esrgan/realesrgan-ncnn-vulkan ]; then
  mkdir -p esrgan && cd esrgan
  curl -sSL -o esrgan.zip https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip
  unzip -o -q esrgan.zip && rm esrgan.zip && chmod +x realesrgan-ncnn-vulkan
fi
echo "Tools ready. Run them with tools/.venv/bin/python tools/<tool>.py"
