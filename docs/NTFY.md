# ntfy Endpoint Configuration

> The wake-up channel only. Pings carry references, never task content
> (PROTOCOL.md §2). If ntfy dies, a GitHub poll catches up — nothing is lost.

## Endpoint

| Item | Value |
|---|---|
| Server | `https://ntfy.sh` |
| Topic | `~/.ulp/bridge-ntfy.topic` locally; `bridge-ntfy.topic` section of the booted cold-boot prompt |
| Publish | `POST https://ntfy.sh/<topic>` with the ping JSON as body |
| Subscribe (L) | `GET https://ntfy.sh/<topic>/stream?since=<cursor\|all>` (ndjson stream) |

## Ping schema

```json
{"v":1,"from":"cloud|local","type":"new-task|pr-ready|blocked|reply|status","ref":"issue:N|pr:M|commit:sha","ts":"<ISO-8601 UTC>"}
```

- `v` — protocol version, currently `1`
- `from` — sender role: `cloud` (P) or `local` (L); receivers ignore their own role
- `type` — ping purpose; L's watcher only acts on `from: cloud` pings
- `ref` — pointer to the durable object on GitHub; the ping never carries content
- `ts` — sender timestamp, ISO-8601 UTC (`2026-09-15T09:00:00Z`)

## Publishing examples

```bash
# P → L: new task ready
curl -s -H "Content-Type: application/json" \
  -d '{"v":1,"from":"cloud","type":"new-task","ref":"issue:2","ts":"2026-09-15T09:00:00Z"}' \
  https://ntfy.sh/ulp-bridge-c01cd81a970f

# L → P: PR ready for review (scripts/ping.sh wraps this)
scripts/ping.sh pr-ready pr:7
```

## Security notes

- The topic string is the only access control on ntfy.sh public topics — treat it
  as a secret. Anyone who knows it can publish pings or read the stream.
- This repo is public: never embed the PAT in a ping or in any file here. Keep
  task content in GitHub issues; keep pings reference-only.
- Every ping sent or received is appended to `docs/audit-log.md` (PROTOCOL.md §5).
