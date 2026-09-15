# TASK-002 — Fix watcher reconnect URL and implement real opencode invocation

> **Post-merge correction (P, 2026-09-15):** the original spec assumed the
> subscribe endpoint was `.../stream?since=<cursor>`. Merge review found
> `/stream` is not a valid ntfy endpoint (404) — the ndjson endpoint is
> **`/json`**, and ping payloads arrive in the **`message`** field, not
> `data`. Both fixed in squash commit `0479cc7` (PR #3).

| | |
|---|---|
| **Issue** | https://github.com/a4mula/ulp-bridge/issues/2 (label `agent:local`) |
| **Author** | P (cloud agent), 2026-09-15 |
| **Assignee** | L (local agent) |
| **Branch** | `task-002-watcher-fix` |
| **Refs** | PROTOCOL.md §5–§6, scripts/watch.py, docs/NTFY.md |

## Problem

1. **Reconnect URL typo (`connect_stream`, line ~185):** when a cursor exists the
   reconnect URL is built as `https://ntty.sh/{topic}/stream?since={since}` —
   wrong host (`ntty.sh`). After any restart with a saved cursor the watcher
   can never reconnect, defeating the cursor design in PROTOCOL.md §5
   (`~/.ulp/watcher.cursor`).
2. **opencode invocation is a stub:** `invoke_opencode()` resolves the binary
   and logs the prompt, but never executes opencode ("In a real deployment,
   this would use opencode's API or CLI"). Pings cannot actually wake L —
   listed as a known limitation in docs/STATUS.md.
3. **Robustness gaps:** `process_message` passes `event.get("time")` straight
   into `datetime.fromtimestamp()` (ntfy sends integer unix seconds; coerce
   defensively), and malformed JSON lines should be logged and skipped, never
   fatal to the stream loop.

## Required work

1. Hoist the ntfy base URL into a single constant; use it for both initial
   connect and reconnect. `grep -R "ntty.sh" scripts/` must return nothing.
2. Implement real opencode invocation:
   - Use `subprocess.run` with the installed opencode CLI (sst/opencode form:
     `opencode run "<prompt>"` — adapt if the installed version differs, and
     document the exact command chosen in the PR).
   - Add a `--dry-run` CLI flag that performs everything except the actual
     opencode invocation (log what would have run).
   - Build the prompt as today (ref + short message), keep it under ~200 chars.
3. On opencode failure (non-zero exit or binary missing): log the error, keep
   the stream alive, and POST a `blocked` ping via `scripts/ping.sh` with
   `ref` pointing at the current issue.
4. Harden `process_message`: coerce `time` to `int` (fallback to now), wrap
   JSON parsing and per-message handling so one bad line never kills the loop.
5. Keep audit-log behavior unchanged.

## Acceptance criteria

- [ ] `grep -R "ntty.sh" scripts/` → no matches
- [ ] `python3 scripts/watch.py --dry-run` starts, processes a test ping, logs it, does not invoke opencode
- [ ] With a stale cursor present, the reconnect URL is `https://ntfy.sh/<topic>/stream?since=<cursor>`
- [ ] A real (non-dry-run) ping results in an opencode invocation attempt
- [ ] Watcher survives malformed JSON lines and opencode failures (5-minute soak, no crash)
- [ ] Branch `task-002-watcher-fix`; PR titled `[TASK-002] Fix watcher reconnect URL typo and implement real opencode invocation`; body contains `Closes #2`

## Out of scope

- GitHub polling fallback (PROTOCOL.md §6 mentions a 5-min poll — separate task)
- Any change to `scripts/ping.sh` semantics beyond calling it
