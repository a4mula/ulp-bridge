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
