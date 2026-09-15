# STATUS

> Running state summary — updated at end of each session.

---

## Current State

**Last updated:** 2026-09-15

**Session:** TASK-002 shipped (P + L, first full delegation cycle complete)

---

## Completed

- [x] Bridge repository created: https://github.com/a4mula/ulp-bridge
- [x] Protocol specification written: `PROTOCOL.md`
- [x] ntfy.sh topic configured: `ulp-bridge-c01cd81a970f` (saved to `~/.ulp/bridge-ntfy.topic`)
- [x] ntfy.sh bidirectional test passed
- [x] Watcher script created: `scripts/watch.py`
- [x] Publisher script created: `scripts/ping.sh`
- [x] Cold-boot prompt written: `docs/COLD_BOOT_PROMPT.md`
- [x] Audit log initialized: `docs/audit-log.md`
- [x] Cloud agent PAT generated (fine-grained, scoped to ulp-bridge repo only)
- [x] P booted with cold-boot prompt — rehydrated from repo state
- [x] P review of bridge complete (issue #1 closed)
- [x] Cold-boot prompt template revised; `docs/NTFY.md` added; protocol labels created
- [x] **TASK-002 complete** (issue #2, PR #3, squash-merged as `0479cc7`):
  watcher now subscribes via `/json` (not the 404 `/stream`), reads ping
  payloads from the `message` field, invokes `opencode run "<prompt>"` for
  real, normalizes blocked-ping refs, supports `--dry-run`, hardened stream
  loop with backoff. Verified end-to-end from P's sandbox against the live
  topic (replayed + processed cloud pings, filtered local pings).

---

## Pending

- [ ] **User restarts the watcher on the local machine with merged code** — `git pull && python3 scripts/watch.py` (first run can be `--dry-run` to watch it process pings)
- [ ] Live wake test after cursor hotfix: P sends a real ping → opencode invokes on User's machine
- [ ] End-to-end live test: P sends a real `new-task` ping → watcher wakes → opencode acts on L's machine (the loop runs with no manual relay)
- [ ] Proposed **TASK-003** (awaiting User approval): deploy watcher as a persistent service with auto-restart (cron/systemd/launchd) + GitHub poll fallback for ntfy outages
- [ ] User added as collaborator to ulp-bridge repo (bootstrap token lacked permission — revisit if still needed)

---

## Known Limitations

- Watcher still needs to be started manually on the User's machine (TASK-003 target)
- No GitHub polling fallback yet (ntfy stream only — pings lost if ntfy is down)
- No CI/CD pipeline yet (lightweight resource constraints)
- P and L share the `a4mula` account, so formal GitHub review events are impossible — PR comments are the review channel

---

## Next Steps

1. User restarts the watcher locally (merged code)
2. P delegates a small live test task; the full P → ntfy → watcher → opencode → PR → P loop runs hands-off
3. On User approval: TASK-003 (persistent watcher + poll fallback)
