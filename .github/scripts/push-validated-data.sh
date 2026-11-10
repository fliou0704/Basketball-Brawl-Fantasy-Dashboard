#!/usr/bin/env bash
# Retry only transport/server failures; never force, reset, or rebase data snapshots.
set -euo pipefail
branch="${1:-main}"
head=$(git rev-parse HEAD)
base=$(git rev-parse HEAD^)
log=$(mktemp)
trap 'rm -f "$log"' EXIT
for attempt in 1 2 3; do
  if git push origin "HEAD:$branch" 2>"$log"; then exit 0; fi
  if ! grep -Eqi 'Internal Server Error|HTTP (500|502|503|504)|returned error: (500|502|503|504)|timed out|Connection reset|remote end hung up' "$log"; then
    echo 'Validated data push rejected; non-transient failure requires investigation.' >&2
    exit 1
  fi
  remote=$(git ls-remote origin "refs/heads/$branch" | awk '{print $1}')
  if [ "$remote" = "$head" ]; then echo 'Remote already contains the validated commit.'; exit 0; fi
  if [ "$remote" != "$base" ]; then echo 'Remote advanced or could not be verified; refusing stale snapshot overwrite.' >&2; exit 1; fi
  if [ "$attempt" = 3 ]; then echo 'Validated data push exhausted its retry budget.' >&2; exit 1; fi
  echo "Transient GitHub push failure; retry $attempt of 2."
  sleep "$((attempt * 5))"
done
