# STATUS

> Running state summary — updated at end of each session.

---

## Current State

**Last updated:** 2026-09-15

**Session:** hotfixing live incident — opencode invocation went silent on first real wake

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
- [x] Fresh PAT received → hotfix pushed to `origin/main` = `920af6c` (2026-09-15T05:57Z). Token stored OUTSIDE the repo tree (`~/.ulp/gh-token`, mode 600) — never committed, never enters docs/patches
- [x] User machine findings: 2 orphaned opencode procs from the 00:33 incident found + killed; `opencode run` sanity test PASSED (`bridge alive` via qwen-35b-moe) — opencode itself healthy, silence was purely the watcher's swallowed output
- [x] **LIVE WAKE TEST PASSED (2026-09-15T06:15:00Z)** — ping `nE8GUWZAbeE1` (06:13:12Z) → watcher invoked opencode in 0.3s → agentic run (git log/show/diff, 108s total, rc=0) → L posted structured review of commit 32cf7dc and acknowledged. First fully observable, hands-off P→L cycle. Watcher returned to idle cleanly after processing
- [x] User: pull + restart done (single clean watcher; old instances swept; clone at `/mnt/data-tier/projects/ulp-bridge`)
- [ ] End-to-end live test: P sends a real `new-task` ping → watcher wakes → opencode acts on L's machine (the loop runs with no manual relay)
- [ ] **TASK-003 DELEGATED** (User approved): issue #4 + spec `docs/tasks/TASK-003.md`, new-task ping `EIPdOGhmjaHW` sent 06:22Z. Wave 1 = systemd user service (watch for `pr-ready` ping). Watcher wake budget for this run: 900s (service will self-configure 1800s for future runs)
- [ ] User added as collaborator to ulp-bridge repo (bootstrap token lacked permission — revisit if still needed)

---

## Known Limitations

- Watcher still needs to be started manually on the User's machine (TASK-003 target)
- No GitHub polling fallback yet (ntfy stream only — pings lost if ntfy is down)
- No CI/CD pipeline yet (lightweight resource constraints)
- P and L share the `a4mula` account, so formal GitHub review events are impossible — PR comments are the review channel
- Cursor saves BEFORE processing (at-least-once delivery): a restart re-processes the last ping — wake-ups are idempotent, benign, but expected
- opencode runs in its own process group with stdin=/dev/null and a 900s cap (`ULP_OC_TIMEOUT` env) — long local-model tasks: raise the env var, don't lower the cap below ~300s

---

## Next Steps

1. User pulls `920af6c`, restarts watcher, confirms live `[oc:*]` output on the replayed pings
2. P delegates a small live test task; the full P → ntfy → watcher → opencode → PR → P loop runs hands-off
3. On User approval: TASK-003 (persistent watcher + poll fallback)
