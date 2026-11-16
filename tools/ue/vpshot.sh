#!/usr/bin/env bash
# Real editor-viewport screenshot (includes everything the user sees):
#   tools/ue/vpshot.sh <out.png> x y z pitch yaw [WxH=1280x720]
#
# Requires UE_PROJECT (project root; screenshots are read from
# <UE_PROJECT>/Saved/Screenshots/WindowsEditor). Needs the editor un-minimised,
# or bThrottleCPUWhenNotForeground=false. Viewport FOV is the user's (default 90).
#
# Helper scripts shipped next to this file:
#   ue_unminimize.ps1  restore the editor window before capture
#   ue_vp_cam.py       save/set/restore the viewport camera
set -eu
UE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MSYS_NO_PATHCONV=1

: "${UE_PROJECT:?UE_PROJECT is not set (path to the UE project root)}"
out="${1:?usage: vpshot.sh <out.png> x y z pitch yaw [WxH]}"
shot_dir="$UE_PROJECT/Saved/Screenshots/WindowsEditor"
mkdir -p "$shot_dir" "$(dirname "$out")"

if [ -f "$UE_DIR/ue_unminimize.ps1" ]; then
  powershell -NoProfile -ExecutionPolicy Bypass -File "$UE_DIR/ue_unminimize.ps1" >/dev/null || true
fi
before=$(ls "$shot_dir" 2>/dev/null | wc -l)
if [ -f "$UE_DIR/ue_vp_cam.py" ]; then
  "$UE_DIR/py.sh" "$UE_DIR/ue_vp_cam.py" set "$2" "$3" "$4" "$5" "$6" >/dev/null
fi
sleep 2
node "$UE_DIR/ue.mjs" execute_command "{\"command\":\"HighResShot ${7:-1280x720}\"}" >/dev/null
for _ in $(seq 1 30); do
  sleep 1
  [ "$(ls "$shot_dir" 2>/dev/null | wc -l)" -gt "$before" ] && break
done
if [ -f "$UE_DIR/ue_vp_cam.py" ]; then
  "$UE_DIR/py.sh" "$UE_DIR/ue_vp_cam.py" restore >/dev/null || true
fi
new=$(ls -t "$shot_dir" 2>/dev/null | head -1)
sleep 1
if [ -n "$new" ] && [ "$(ls "$shot_dir" | wc -l)" -gt "$before" ]; then
  cp "$shot_dir/$new" "$out"
  echo "ok $out"
else
  echo "no screenshot (viewport not rendering?)"
  exit 1
fi
