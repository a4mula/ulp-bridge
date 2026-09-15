# STATUS

> Running state summary — updated at end of each session.

---

## Current State

**Last updated:** 2026-09-15

**Session:** Onboarding + first delegation (P — cloud agent)

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
- [x] Cloud agent topic pasted into `docs/COLD_BOOT_PROMPT.md` (boot-time secret sections defined)
- [x] P (Project Lead) booted with cold-boot prompt — rehydrated from repo state
- [x] P review of bridge complete (see issue #1 close comment): watcher reconnect typo found, opencode stub confirmed, missing `docs/NTFY.md` added, cold-boot prompt template revised, protocol labels created
- [x] First task delegation from P to L: **TASK-002** (issue #2), `new-task` ping sent 2026-09-15T04:52:06Z (ntfy id 1kBaNLjGLwGE)

---

## Pending

- [ ] L executes TASK-002: fix `watch.py` reconnect URL typo (`ntty.sh`), implement real opencode invocation, harden stream loop — spec: `docs/tasks/TASK-002.md`
- [ ] P reviews TASK-002 PR (squash-merge per PROTOCOL.md §4)
- [ ] User added as collaborator to ulp-bridge repo (bootstrap token lacked permission — revisit if still needed)
- [ ] End-to-end live test: P ping → watcher wakes → opencode runs on User's machine (blocked until TASK-002 lands)

---

## Known Limitations

- `scripts/watch.py` opencode invocation is a stub until TASK-002 merges — pings are logged, not acted on
- No GitHub polling fallback yet (ntfy stream only)
- No CI/CD pipeline yet (lightweight resource constraints)

---

## Next Steps

1. User runs/relays L on User's machine: read issue #2 + `docs/tasks/TASK-002.md`, branch `task-002-watcher-fix`, PR with `Closes #2`
2. P reviews and squash-merges; pings `pr-ready` / `blocked` per PROTOCOL.md §3
3. End-to-end live test of the wake-up channel
