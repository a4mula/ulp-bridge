# TASK-003 — Persistent watcher service + GitHub polling fallback

| | |
|---|---|
| **Issue** | https://github.com/a4mula/ulp-bridge/issues/4 (label `agent:local`) |
| **Author** | P (cloud agent), 2026-09-15 (approved by User same day) |
| **Assignee** | L (local agent) |
| **Branch** | `task-003-persistent-watcher` |
| **Refs** | scripts/watch.py, scripts/ping.sh, PROTOCOL.md §5–§6, docs/NTFY.md, audit-log entries 06:00Z–06:15Z |

## Problem

The bridge currently exists only while a User terminal runs `python3
scripts/watch.py` in the foreground:

1. **Fragile lifetime** — closing the terminal, logging out, or a reboot
   silences the bridge with no auto-recovery. L stops existing as a
   reachable agent until a human remembers to restart it.
2. **Single channel** — the ntfy stream is the only ingest path. If ntfy.sh
   is down or unreachable, pings are lost and P has no durable way to reach
   L (the durable state lives in GitHub issues/comments, but nothing polls
   it).
3. **Background evidence** (audit log): on 2026-09-15 an un-killed old
   watcher instance raced a new one and double-consumed a ping. A
   supervised service with a single-consumer rule prevents this class of
   accident.

## Required work

### Part A — persistent service (wave 1)

1. Detect the init environment. **Preferred: systemd user service.**
   Create `~/.config/systemd/user/ulp-watcher.service`:

   ```ini
   [Unit]
   Description=ULP Bridge Watcher (L)
   After=network-online.target

   [Service]
   ExecStart=/usr/bin/python3 /mnt/data-tier/projects/ulp-bridge/scripts/watch.py
   WorkingDirectory=/mnt/data-tier/projects/ulp-bridge
   Environment=ULP_OC_TIMEOUT=1800
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=default.target
   ```

   - Use the real absolute python3 path on robb-dev (`command -v python3`),
     and the real repo path (`/mnt/data-tier/projects/ulp-bridge`).
   - `Environment=ULP_OC_TIMEOUT=1800` — future service-run invocations get
     a 30-minute budget (self-referential: the service L deploys configures
     its own future wake-ups).
2. Enable: `systemctl --user daemon-reload && systemctl --user enable --now
   ulp-watcher`. Verify with `systemctl --user status ulp-watcher` and
   `journalctl --user -u ulp-watcher -n 20`.
3. Attempt `loginctl enable-linger $USER` so the service starts at boot
   without an active login session. This may require sudo; if it fails or
   prompts for a password, DO NOT block — document the outcome in the PR
   (service still auto-starts at login without linger).
4. **Single-consumer rule (critical):** before enabling the service, all
   foreground watcher instances MUST be stopped (`pkill -f
   'scripts/watch.py'`). Two concurrent consumers double-process pings —
   this exact failure happened at 06:00Z (audit log). Document the
   kill-then-enable order in `docs/SERVICE.md`.
5. **Cron fallback** (only if systemd user units are unavailable): a
   supervisor script (`scripts/watch-supervisor.sh`: `while true; do
   python3 scripts/watch.py >> ~/.ulp/watcher.log 2>&1; sleep 10; done`,
   started via `@reboot` cron line). robb-dev almost certainly has systemd;
   keep this branch minimal.

### Part B — GitHub polling fallback (wave 2)

1. New script `scripts/poll_github.py`:
   - Reads the token from `~/.ulp/gh-token` (plain file, machine-local,
     NEVER committed or logged). **If the file is missing or empty: log a
     warning and exit 0** — polling is optional, absence must never crash
     or block.
   - Persisted state in `~/.ulp/poll.cursor` (unix seconds of last
     successful poll) and `~/.ulp/poll.seen` (JSON list of processed item
     ids, prune to last 500).
   - Each run polls (GitHub API `since` here IS an ISO timestamp — unlike
     ntfy's unix seconds):
     - `GET /repos/a4mula/ulp-bridge/issues?labels=agent:local&state=all&since=<iso>` — new/updated issues
     - `GET /repos/a4mula/ulp-bridge/pulls/comments?since=<iso>` — PR review comments
     - `GET /repos/a4mula/ulp-bridge/issues/comments?since=<iso>` — issue/PR conversation comments
   - For each NEW item (id not in seen): append an audit-log entry, then
     wake L by importing the existing path — `from watch import
     invoke_opencode, append_audit_log` (same directory; reuse, do not
     duplicate). Ref mapping: issue → `issue:N`, PR review comment →
     `pr:N` (use the PR number from the comment's `pull_request_url`),
     issue comment on a PR conversation → `pr:N` if `issue.pull_request`
     is set else `issue:N`.
   - Update the cursor only after the full cycle completes successfully.
2. Schedule — systemd user timer (preferred):

   ```ini
   # ~/.config/systemd/user/ulp-poll.timer
   [Unit]
   Description=Poll GitHub for missed bridge events (every 5 min)

   [Timer]
   OnCalendar=*:0/5
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

   plus `ulp-poll.service` (`Type=oneshot`, `ExecStart=/usr/bin/python3
   /mnt/data-tier/projects/ulp-bridge/scripts/poll_github.py`,
   `WorkingDirectory` = repo root). Enable with `systemctl --user enable
   --now ulp-poll.timer`. Cron `*/5 * * * *` as the documented fallback.
3. **Race semantics:** stream and poll may both wake L for the same event —
   acceptable and intentional (at-least-once delivery; wake-ups are
   idempotent "read it, act, report"). Best-effort dedup via seen-ids is
   enough; do NOT build a coordination service.

### Docs

- New `docs/SERVICE.md`: unit files (paths + contents), install/enable
  commands, verification commands, how to stop everything (`systemctl --user
  disable --now ulp-watcher ulp-poll.timer`), troubleshooting
  (journalctl, single-consumer rule, token placement).
- Update `docs/STATUS.md` (Pending section) in the PR.

## Delivery (waves — the 900s per-wake budget is real)

Wave 1 = Part A. Commit it, push the branch, open a **draft PR**, and ping
`pr-ready` via `scripts/ping.sh`. If ≥ ~700s of the current wake have
elapsed at that point, stop there — P will re-wake you for wave 2 (the
service unit you just installed raises the budget to 1800s for all future
runs). If time remains, proceed to wave 2 in the same wake.

On any blocker: commit what works, ping `blocked` with the ref, describe
the blocker in the PR.

### Auth notes (robb-dev)

1. Before starting work: `cd /mnt/data-tier/projects/ulp-bridge && git
   pull --ff-only origin main` so the spec you are reading is the latest
   revision.
2. If `git push` fails on the clone's stored credentials, use the
   machine-local token (lives at `~/.ulp/gh-token`, mode 600 — NEVER
   print it, NEVER commit it, NEVER put it in the remote URL of a
   tracked file):

   ```
   TOKEN=$(cat ~/.ulp/gh-token)
   git push https://x-access-token:${TOKEN}@github.com/a4mula/ulp-bridge.git task-003-persistent-watcher
   ```

3. Draft PR via the REST API with the same token (`gh` CLI may not be
   installed):

   ```
   curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/a4mula/ulp-bridge/pulls \
     -d '{"title":"[TASK-003] Persistent watcher service + GitHub polling fallback","head":"task-003-persistent-watcher","base":"main","draft":true,"body":"Closes #4\n\nWave 1: systemd user service (Part A).\nWave 2: GitHub polling fallback (Part B)."}'
   ```

4. If `~/.ulp/gh-token` is missing or empty: skip steps 2–3, commit your
   work locally, and ping `blocked` with the reason — the User is placing
   the token; a later wake (replayed or fresh ping) will succeed.

## Acceptance criteria

- [ ] `systemctl --user is-enabled ulp-watcher` → `enabled`; `is-active` → `active`
- [ ] `pkill -f watch.py` → process auto-restarts within ~15s (fresh PID, `Restart=always` verified live)
- [ ] Exactly ONE watcher consumer exists after install (foreground instances killed first)
- [ ] Linger attempted; outcome (success or fallback note) documented in the PR
- [ ] `scripts/poll_github.py`: with `~/.ulp/gh-token` present, a manual run creates `~/.ulp/poll.cursor`, detects new items once, and invokes opencode exactly once per new item; without the token it exits 0 with a warning
- [ ] `ulp-poll.timer` enabled (`systemctl --user list-timers` shows it) or cron fallback documented
- [ ] `git grep -i 'github_pat\|ghp_'` over the branch → no matches (tokens never enter the repo)
- [ ] `docs/SERVICE.md` covers install, verify, stop, troubleshoot
- [ ] PR titled `[TASK-003] Persistent watcher service + GitHub polling fallback`; body contains `Closes #4`

## Out of scope

- P-side repo-watch cron (P's own polling — separate proposal)
- Cross-machine / multi-L support
- Strong dedup/coordination between stream and poll (at-least-once is the design)
- Any change to ping payload format
