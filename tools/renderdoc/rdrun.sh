#!/usr/bin/env bash
# Usage: tools/renderdoc/rdrun.sh <script.py> [timeout_sec]
#
# Runs a RenderDoc Python script inside qrenderdoc. Environment variables are
# passed through to the script (see each rd_*.py for the ones it reads:
# RDC, OUTDIR, OUT, EID, IDS, E0, E1, ...).
#
# RENDERDOC_DIR  directory that holds qrenderdoc(.exe). If unset, qrenderdoc is
#                looked up on PATH.
#
# Runs are serialised with a mkdir lock: replaying a multi-GB capture costs
# several GB of RAM, so two at once will swap the machine. A hung run is killed
# on timeout -- note that a Python syntax error leaves qrenderdoc waiting, which
# is the usual cause of a timeout.

set -u

SCRIPT="${1:?usage: rdrun.sh <script.py> [timeout_sec]}"
TIMEOUT="${2:-300}"
LOCK="${TMPDIR:-/tmp}/rdrun.lock"

if [ -n "${RENDERDOC_DIR:-}" ]; then
  QRENDERDOC="$RENDERDOC_DIR/qrenderdoc"
  [ -x "$QRENDERDOC" ] || QRENDERDOC="$RENDERDOC_DIR/qrenderdoc.exe"
else
  QRENDERDOC="$(command -v qrenderdoc || command -v qrenderdoc.exe || true)"
fi

if [ -z "${QRENDERDOC:-}" ] || [ ! -x "$QRENDERDOC" ]; then
  echo "qrenderdoc not found; set RENDERDOC_DIR to the RenderDoc install directory" >&2
  exit 127
fi

for _ in $(seq 1 600); do
  if mkdir "$LOCK" 2>/dev/null; then break; fi
  sleep 2
done
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

timeout "$TIMEOUT" "$QRENDERDOC" --python "$SCRIPT"
rc=$?
if [ "$rc" -eq 124 ]; then
  taskkill //F //IM qrenderdoc.exe >/dev/null 2>&1 || pkill -f qrenderdoc >/dev/null 2>&1 || true
  echo "TIMEOUT (killed qrenderdoc). Check script syntax first: a syntax error leaves qrenderdoc hanging." >&2
fi
exit "$rc"
