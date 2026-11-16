#!/usr/bin/env bash
# usage: tools/ue/py.sh <script.py> [args...]  -> runs run(*args) in the editor, prints result
#
# Requires UE_PROJECT for the bridge (see ue.mjs). The script path is made
# absolute relative to the caller's working directory, so run this from the
# repository root.
set -eu
UE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$UE_DIR/../.." && pwd)"
export MSYS_NO_PATHCONV=1

src="$1"; shift
# Accept paths relative to the caller's cwd, or relative to the repository root.
if [ ! -f "$src" ] && [ -f "$ROOT/$src" ]; then src="$ROOT/$src"; fi
if [ ! -f "$src" ]; then
  echo "no such script: $src" >&2
  exit 1
fi
f=$(cygpath -m "$(cd "$(dirname "$src")" && pwd)/$(basename "$src")")
args=$(node -e 'console.log(JSON.stringify(process.argv.slice(1)))' -- "$@")
node "$UE_DIR/ue.mjs" run_python_file "{\"filePath\":\"$f\",\"entryPoint\":\"run\",\"args\":$args,\"captureLog\":true}" | node -e '
let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{const j=JSON.parse(s);const r=j.result||{};if(j.error){console.log("ERROR",JSON.stringify(j.error));return;}console.log(r.result);if(r.logErrorCount||!r.success)console.log("LOG",JSON.stringify(r.log_output||r).slice(0,3000));}catch(e){console.log(s)}})'
