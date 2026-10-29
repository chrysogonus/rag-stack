#!/usr/bin/env bash
# The weekly refresh on the server (rag-stack-refresh.service): ingest, build, check and score a
# new index generation, and restart the API if it was promoted, so it loads the new edges.
# Like `make refresh`, for the Compose deployment. Run from the repo checkout with its .env.
set -euo pipefail
cd "$(dirname "$0")/../.."

docker compose run --rm -T migrate
code=0
line=$(docker compose run --rm --no-deps -T api python -m rag_stack.cli refresh "$@" | tee /dev/stderr | tail -n 1) || code=$?
if [[ $line =~ ^[^|]*\ PROMOTED ]]; then
	docker compose restart api
fi
exit $code
