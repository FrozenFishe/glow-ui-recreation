#!/bin/sh
# shot.sh <url-query> <out.png>: Chrome headless at 1x, 1672x941 (the design size)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1672,941 --virtual-time-budget=4000 --screenshot="$2" "http://localhost:8788/$1" >/dev/null 2>&1
