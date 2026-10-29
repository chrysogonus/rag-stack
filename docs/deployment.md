# Deploying on one VM

The public chatbot runs as Docker Compose on a single Linux VM, from a published image. What
identifies a deployment (its domain, secrets, Impressum and privacy policy) stays out of this
repository: `.env` on the server, and the legal pages in a folder of their own (e.g. a private
repository).

## What runs

| Service | What it does | Reachable from |
|---|---|---|
| `caddy` | TLS (Let's Encrypt), security headers, `/impressum` and `/datenschutz`, proxy to `api` (`deploy/Caddyfile`) | the internet: 80, 443 |
| `api` | The image `ghcr.io/<owner>/rag-stack`: FastAPI, the built web UI and the CPU models (cached in the `models` volume) | `caddy` only |
| `migrate` | `alembic upgrade head` once per start; `api` waits for it | – |
| `postgres` | Conversations (LangGraph checkpointer) and the edge table | the VM (127.0.0.1) |
| `qdrant` | The knowledge base, one collection per index generation | the VM (127.0.0.1) |
| `langfuse-*` | Self-hosted tracing and the readers' ratings | the VM: UI on 127.0.0.1:3000 |

The CLI runs in the same image: `docker compose run --rm --no-deps -T api python -m rag_stack.cli <command>`.
The knowledge base is built on the server by the refresh (`deploy/server/refresh.sh`), which
writes to the `kb_data` volume.

Constraints:

- **One API process.** Rate limits and token budgets live in its memory (`api/limits.py`).
  More replicas need a shared store first.
- **Client IPs.** Caddy sets `X-Forwarded-For`; the API trusts it only from private networks
  (`FORWARDED_ALLOW_IPS`). Docker publishes ports with NAT for IPv4, so the API sees real
  addresses. Over IPv6, Docker's userland proxy would hide them; keep the VM on IPv4 or check.
- **Docs.** FastAPI's `/docs` and `/openapi.json` are not published (Caddy answers 404).

## Server

A VM with about 8 vCPU and 32 GB RAM: the API holds the embedding and reranking models, the
weekly refresh loads a second copy, and Langfuse's ClickHouse wants several GB. About 100 GB
of disk. Then:

1. Allow inbound 80/tcp, 443/tcp and 443/udp from anywhere, and SSH only from where you
   administer it. Nothing else: Postgres, Qdrant and Langfuse bind to 127.0.0.1.
2. Install Docker Engine with the Compose plugin and automatic security updates. Add the
   deploy user to the `docker` group.
3. Point the domain's A record at the VM's static IP.
4. Schedule daily disk snapshots (Postgres and the Langfuse stores hold the only data that
   can't be rebuilt; the index can be, with a refresh). Their retention belongs in the privacy
   policy.

## First deployment

```bash
sudo install -d -o "$(id -un)" /opt/rag-stack
git clone https://github.com/<owner>/rag-stack /opt/rag-stack && cd /opt/rag-stack
git checkout v<version>            # the Compose files and Caddyfile of the deployed version
cp .env.production.example .env    # fill in every <...>; chmod 600 .env
docker compose pull
docker compose up -d postgres qdrant
deploy/server/refresh.sh           # builds the knowledge base: about an hour on CPU
docker compose up -d               # Caddy obtains the certificate on first start
```

`refresh.sh` must end in `PROMOTED`. The API's first start downloads the models (a few GB)
before `/api/health` answers 200; its healthcheck allows ten minutes.

Then install the timers (weekly refresh, daily retention):

```bash
for unit in deploy/server/*.service deploy/server/*.timer; do
  sed -e "s|@REPO@|$PWD|" -e "s|@USER@|$(id -un)|" "$unit" | sudo tee "/etc/systemd/system/$(basename "$unit")" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now rag-stack-refresh.timer rag-stack-prune.timer
```

Langfuse's UI: `ssh -L 3000:127.0.0.1:3000 <vm>`, then http://localhost:3000 with
`LANGFUSE_ADMIN_EMAIL`. Sign-up is off (`LANGFUSE_DISABLE_SIGNUP=true`).

## Check before publishing

- `curl -I https://<domain>/` shows HSTS and the CSP; `/docs` and `/openapi.json` answer 404.
- An answer streams word by word in the browser, its sources light up, and a rating returns
  204 and shows in Langfuse.
- From outside, only ports 80 and 443 (and SSH from your address) are open.
- The eleventh question within a minute gets "Too many requests", from each of two networks
  separately.
- After `sudo reboot`, every service comes back and `/api/health` answers 200.
- `/impressum` and `/datenschutz` load, and the footer links to them.

## Releases and updates

A `v*` tag on GitHub runs CI and, if every check passes, publishes the image to GHCR, scanned
by Trivy, with provenance and an SBOM. There is no `latest`. To deploy one:

```bash
cd /opt/rag-stack
git fetch --tags && git checkout v<version>
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=<version>/' .env
docker compose pull && docker compose up -d
```

To roll back, do the same with the previous version. Migrations run forward only; restore a
snapshot if a release changed the schema.

Caddy and the database images are pinned by digest in the Compose files; Dependabot proposes
updates, which reach the server with the next release.

## Knowledge base

- **Refresh**: `rag-stack-refresh.timer`, Sundays 03:00. It ingests every source, builds a new
  generation, scores it on the golden set, promotes it only if it passes the thresholds, and
  restarts the API. Results: `refresh.log` in the `kb_data` volume, and
  `journalctl -u rag-stack-refresh`.
- **Rollback**: `docker compose run --rm --no-deps -T api python -m rag_stack.cli rollback`,
  then `docker compose restart api`.
- A new embedding model rebuilds the whole index; the refresh handles it.

## Retention

`rag-stack-prune.timer` runs `prune` daily at 04:30. It deletes conversations whose last turn
is older than `CONVERSATION_RETENTION_DAYS` and traces (questions, answers, retrieved passages
and ratings) older than `TRACE_RETENTION_DAYS`. Self-hosted Langfuse has no retention setting of
its own (an Enterprise feature), so `prune` deletes through its API. Rate limiting keeps client
addresses in memory only, for at most a day. Neither Caddy nor the API writes an access log, and
container logs are capped at 3 × 10 MB per service.

The browser keeps the list of a reader's chats in `localStorage`; there are no cookies.
