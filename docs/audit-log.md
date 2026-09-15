# Audit Log

## 2026-09-15T04:19:05Z

test → issue:bootstrap
  ```
{"v":1,"from":"local","type":"test","ref":"issue:bootstrap","ts":"2026-09-15T04:19:05Z"}
  ```

## 2026-09-15T04:21:32Z

bootstrap-complete → issue:1
  ```
{"v":1,"from":"local","type":"bootstrap-complete","ref":"issue:1","ts":"2026-09-15T04:21:32Z"}
  ```

## 2026-09-15T04:52:06Z

new-task → issue:2  (sent by P — ntfy id 1kBaNLjGLwGE)
  ```
{"v":1,"from":"cloud","type":"new-task","ref":"issue:2","ts":"2026-09-15T04:52:06Z"}
  ```

## 2026-09-15T05:08:55Z

review → pr:3  (sent by P — review comment id 5675066281, 2 changes requested)
  ```
{"v":1,"from":"cloud","type":"review","ref":"pr:3","ts":"2026-09-15T05:08:55Z"}
  ```

## 2026-09-15T05:19:18Z

status → commit:0479cc7  (sent by P — PR #3 squash-merged, issue #2 closed)
  ```
{"v":1,"from":"cloud","type":"status","ref":"commit:0479cc7","ts":"2026-09-15T05:19:18Z"}
  ```

## 2026-09-15T05:33:08Z

status → commit:dbfdfcd  (sent by P — LIVE wake test to running watcher; payload repaired — heredoc had mangled this entry)
  ```
{"v":1,"from":"cloud","type":"status","ref":"commit:dbfdfcd","ts":"2026-09-15T05:33:08Z"}
  ```

## 2026-09-15T05:55:00Z

incident + hotfix (logged by P) — watcher invoked opencode (ref=commit:dbfdfcd) then went silent

  ```
Watcher (User machine, unpatched main dbfdfcd):
  00:33:09 [INFO] Invoking opencode with ref=commit:dbfdfcd
  ... no further output, no success/rc/timeout log, NO blocked ping on topic

Topic history polled via ntfy /json?poll=1&since=all — last message is the
05:33:08Z status ping; zero local pings after it => 120s timeout path never
completed => User stopped the watcher before then; opencode tree left
orphaned, its output invisible (capture_output=True swallowed everything).

Root causes (old invoke_opencode):
  1. capture_output=True — zero observability
  2. timeout=120s — too short for local-model agentic runs
  3. no cleanup on watcher exit — Ctrl+C orphans the opencode tree
  4. _post_blocked_ping mangled commit:/pr: refs (issue:commit:X)

Hotfix 32cf7dc (scripts/watch.py only): live [oc:out]/[oc:err] streaming,
60s heartbeats, ULP_OC_TIMEOUT (default 900s), process-group SIGKILL on
timeout AND on watcher exit, stdin=DEVNULL, ref passthrough, bounded
post-kill path. Verified vs fake-opencode: ok/fail/hang-with-pipe-child
(kill at 5s exact, zero strays). Old-code stray reproduction: kill(parent)
orphaned the pipe-holding child (ps-verified).
  ```

## 2026-09-15T05:58:05Z

status → commit:32cf7dc  (sent by P — hotfix pushed to origin/main 920af6c; fresh wake ping for patched watcher; ntfy id 6dGEU86kHQci)
  ```
{"v":1,"from":"cloud","type":"status","ref":"commit:32cf7dc","ts":"2026-09-15T05:58:05Z"}
  ```

## 2026-09-15T05:58:40Z

deploy notes (logged by P) — hotfix live on GitHub, User deployment pending

  ```
- Fresh fine-grained PAT received from User; stored at ~/.ulp/gh-token
  (mode 600, OUTSIDE the repo tree — never committed; token absent from
  all docs, commits, and exported patches per User's explicit requirement)
- Pushed 183dca1..920af6c to origin/main (fast-forward, verified ls-remote)
- User machine report: 2 orphaned /snap/opencode/217/bin/opencode procs
  from the 00:33 incident found via pgrep and killed; opencode run sanity
  test PASSED ("bridge alive", model line: build · qwen-35b-moe) =>
  opencode + provider healthy; incident was watcher-side observability only
- Awaiting: User git pull + watcher restart; watcher will replay 05:33 +
  05:58 pings (at-least-once cursor semantics) as the live retest
  ```

## 2026-09-15T06:00:05Z

blocked → issue:commit:32cf7dc  (RECEIVED by P from L's old-code watcher — user clone at /mnt/data-tier/projects/ulp-bridge consumed the 05:58 ping before restarting; opencode timed out at exactly 120s per old code; mangled ref fingerprints pre-pull version. First fully relay-free L→P failure report. Ref mangling expected in old code, fixed in 32cf7dc)
  ```
{"v":1,"from":"local","type":"blocked","ref":"issue:commit:32cf7dc","ts":"2026-09-15T06:00:05Z"}
  ```

## 2026-09-15T06:13:12Z

status → commit:32cf7dc  (sent by P — live wake test against SINGLE clean patched watcher; ntfy id nE8GUWZAbeE1; User confirmed old instances killed via pkill before this send)
  ```
{"v":1,"from":"cloud","type":"status","ref":"commit:32cf7dc","ts":"2026-09-15T06:13:12Z"}
  ```

## 2026-09-15T06:15:00Z

LIVE WAKE TEST PASSED (logged by P) — first fully observable hands-off cycle

  ```
06:13:12.435Z watcher: Invoking opencode with ref=commit:32cf7dc (0.3s after ping)
              opencode: bin=/snap/bin/opencode timeout=900s cwd=/mnt/data-tier/projects/ulp-bridge prompt_chars=122
06:13:13     [oc:err] > build · qwen-35b-moe   (opencode banner, streamed live)
06:14:12     heartbeat: still running 60s elapsed
06:14:21     [oc:err] $ git log --oneline -10
06:14:22     [oc:err] $ git show 32cf7dc --stat
06:14:27     [oc:err] $ git diff 183dca1..32cf7dc -- scripts/watch.py
06:14:59     [oc:out] structured review of 32cf7dc (root causes, before/after table)
06:15:00     opencode finished OK (rc=0, 108s) — watcher idle again

Notes:
- 108s runtime vs old 120s cap: old code would have killed this run with 12s
  of margin — the 900s default was not paranoia
- L's final line: "Cloud ping acknowledged. Status: commit reviewed, no
  action needed beyond awareness."
- Bridge loop P→ntfy→watcher→opencode→(report) verified with zero human relay
  ```


## 2026-09-15T06:22:30Z

task delegation (logged by P) — TASK-003 approved by User, issue #4 opened

  ```
Issue #4: [TASK-003] Persistent watcher service + GitHub polling fallback
Labels: agent:local
Spec: docs/tasks/TASK-003.md (committed in the next push)
Delivery: wave 1 = systemd user service (draft PR + pr-ready ping),
          wave 2 = GitHub polling fallback (timer + poll_github.py)
new-task ping follows once this push lands
  ```
