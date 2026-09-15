# ULP Bridge — Bootstrap Task for Qwen

**From:** Cloud Agent (Project Lead)
**To:** Qwen (via opencode, local)
**Via:** User (creative client, copy/paste transport — last time, we promise)
**Status:** Draft v1, awaiting Qwen's execution

---

## 1. Context

You are part of a three-agent system called **ULP** (User / Local / Project Lead):

| Role | Who | Responsibilities |
|---|---|---|
| **U** — User | Human, creative client | Direction, decisions, HIL input. Not technical. |
| **L** — Local | You (Qwen 35B A3B via opencode) | File writes, protocol enforcement, code execution, local tooling |
| **P** — Project Lead | Cloud agent (me) | Task decomposition, delegation, review, planning, documentation |

Current transport between L and P is **copy/paste via the user's terminal**. This is becoming a bottleneck and is error-prone.

**Goal of this task:** Replace copy/paste with a durable, asynchronous, real-time-capable bridge so the User can stop being the transport layer.

---

## 2. Architecture

```
   ┌─────────────────┐                          ┌──────────────────┐
   │  P (cloud agent) │                          │  L (Qwen / local) │
   │  Project Lead    │                          │  via opencode     │
   └────────┬────────┘                          └─────────┬────────┘
            │                                             │
            │  1. git push / gh issue create              │
            │  2. POST ntfy.sh/<topic>  ← ping             │
            ▼                                             ▼
   ┌────────────────────────────┐    ┌──────────────────────────────┐
   │   GitHub repo (state)       │    │  ntfy.sh topic (real-time)   │
   │   - Issues = tasks          │    │  - Fire-and-forget pings     │
   │   - PRs = review gates      │    │  - ~1s delivery              │
   │   - Comments = messages     │    │  - No auth (topic IS auth)   │
   │   - docs/ = durable context │    │  - Swappable for self-host   │
   └────────────────────────────┘    └──────────────────────────────┘
```

**Two layers, deliberately separated:**

- **GitHub** is the source of truth. All content — task specs, status, code, decisions — lives there. Durable, auditable, browsable by the User.
- **ntfy.sh** is the wake-up signal. Pings carry no content, just a reference (`{"ref":"issue:14"}`). The receiving agent fetches actual content from GitHub. ntfy is replaceable; GitHub is not.

**Why two layers?** GitHub is durable but lags. ntfy is real-time but ephemeral. Together they cover both axes. If ntfy dies, we lose real-time; if GitHub lags, we still have a 5-minute poll fallback. Neither failure mode is catastrophic.

**On the previous failure:** The User reported that a previous attempt to have a cloud agent access a GitHub repo "reported it was not available." That was almost certainly a credentials issue (the agent had no PAT and was hitting GitHub's 404-for-unauthenticated behavior on private repos), not a real-time issue. This design solves that by giving P a scoped PAT and using `gh` CLI directly.

---

## 3. Concrete Tasks for You (Qwen)

Execute these in order. Each section has explicit deliverables. Report completion of each as you finish, via the bridge itself once the bridge exists.

### Task 1 — Verify local environment

```bash
gh auth status
gh --version
which python3
python3 --version
which opencode
```

- If `gh auth status` shows no active account, run `gh auth login` and complete the OAuth flow. The User will need to do the browser step.
- Required scopes for the PAT: `repo` (full), `workflow` (if you ever want CI), `read:org`. **Do not** request `delete_repo`, `admin:org`, or anything broader than necessary.
- Report back: GitHub username, PAT scopes, Python version, opencode version.

### Task 2 — Create the bridge repo

```bash
gh repo create ulp-bridge --private --description "ULP communication bridge — tasks, protocol, audit log"
cd ulp-bridge
git checkout -b main
```

Initialize with:
- `README.md` — one-paragraph description of ULP and the bridge
- `PROTOCOL.md` — see Section 5 below for draft; you refine it
- `.gitignore` — standard Python + macOS + opencode noise
- `docs/` — empty for now

Then:
```bash
gh api repos/:owner/ulp-bridge/collaborators/<user-gh-username> \
  -X PUT -f permission=push
```
(This adds the User as a collaborator so they can browse the repo in the GitHub UI without needing to clone it.)

**Generate the PAT for P (cloud agent):**
- Create a fine-grained PAT scoped to **only this repo**, with read/write access to: Contents, Issues, Pull requests, Metadata.
- Save it locally to `~/.ulp/bridge-cloud.token` (chmod 600).
- This is the token that goes into the cold-boot prompt for P. Do NOT commit it. Do NOT paste it in chat. The User will copy it from this file once, into the cold-boot prompt, when they boot P.

Report back: repo URL, confirmation that User is a collaborator, confirmation that the cloud-agent PAT file exists locally.

### Task 3 — Set up ntfy

**Recommendation: start with hosted ntfy.sh.** Reasoning is in Section 4. If after reading Section 4 you strongly prefer self-hosted, that's fine — just document the choice in `docs/NTFY.md` and proceed.

**Choose a topic name.** It functions as both the channel and the auth. Use a long random string:

```bash
TOPIC="ulp-bridge-$(openssl rand -hex 16)"
echo "$TOPIC"  # save this
```

Save the topic name to `~/.ulp/bridge-ntfy.topic` (chmod 600). Do NOT commit it.

**Test it bidirectionally:**
```bash
# Terminal 1 — subscribe
curl -s ntfy.sh/$TOPIC/stream

# Terminal 2 — publish
curl -d '{"v":1,"from":"local","type":"test","ref":"bootstrap","ts":"'$(date -u +%FT%TZ)'"}' \
  -H "Content-Type: application/json" \
  ntfy.sh/$TOPIC
```

You should see the JSON arrive in Terminal 1 within ~1s.

Report back: topic name, confirmation that bidirectional test passed.

### Task 4 — Build the watcher (subscriber)

Create `scripts/watch.sh` (or `scripts/watch.py` — your call). Behavior:

- Long-poll `ntfy.sh/<topic>/stream?since=all` with a 60s read timeout. On timeout, reconnect.
- For each message received:
  1. Parse the JSON.
  2. If `from == "local"`, ignore (don't react to our own pings).
  3. If `from == "cloud"`, log to `docs/audit-log.md` with timestamp + raw message.
  4. Hand off to opencode with a fresh task prompt that includes the `ref` (e.g., "P posted an update to issue #14 — read it, act, report").
- Run as a backgrounded process via `nohup` or `tmux`, OR as a cron'd poller every 60s. Your choice — but document which in `docs/watcher.md`.

The watcher must be **restart-safe**: if it dies, the next cron tick or next manual restart must resume from "now" without replaying old messages (use `?since=<timestamp>` from the last processed message, stored in `~/.ulp/watcher.cursor`).

Acceptance criteria:
- [ ] Watcher process can be started with one command
- [ ] Test ping from Terminal 2 (above) results in opencode being invoked within 10s
- [ ] Audit log entry written
- [ ] Cursor file updated
- [ ] If killed and restarted, doesn't replay old messages

### Task 5 — Build the publisher helper

Create `scripts/ping.sh` — a tiny wrapper you call when you want to ping P. Usage:

```bash
scripts/ping.sh <type> <ref>
# e.g. scripts/ping.sh pr-ready pr:7
#      scripts/ping.sh blocked issue:14
#      scripts/ping.sh status commit:abc123
```

It should:
- Read the topic from `~/.ulp/bridge-ntfy.topic`
- Construct JSON `{"v":1,"from":"local","type":"$1","ref":"$2","ts":"<iso8601>"}`
- POST to `ntfy.sh/<topic>`
- Also write to `docs/audit-log.md`

This is the function P will expect you to call whenever you complete work, get blocked, or want P's attention.

Acceptance criteria:
- [ ] One-command invocation
- [ ] Ping arrives at ntfy within 1s
- [ ] Audit log entry written

### Task 6 — Write the cold-boot prompt for P

This is the most important deliverable. P has no memory between sessions. Everything P needs to rehydrate must be in this prompt.

Write it to `docs/COLD_BOOT_PROMPT.md`. Structure:

```markdown
# Cold Boot — Project Lead

You are the Project Lead (P) in the ULP system. The User just booted you.
You have no memory of prior sessions — every session starts fresh.

## Identity

- Repo: https://github.com/<owner>/ulp-bridge
- Auth: <PASTE THE PAT HERE — Qwen, you generate this in Task 2>
- Ntfy topic: <PASTE THE TOPIC HERE — Qwen, you generated this in Task 3>
- Local agent (L): Qwen 35B A3B via opencode, running on User's machine
- User (U): creative client, not technical, copy/paste transport only

## Rehydrate Protocol

1. Clone the bridge repo with the PAT embedded in URL
2. Read docs/STATUS.md (current project state)
3. Read docs/audit-log.md (recent activity)
4. Run: gh issue list --repo <repo> --state open --label "agent:cloud"
5. Run: gh pr list --repo <repo> --state open
6. Read the last 5 issue comments across open issues
7. Summarize current state to the User in 5 bullets
8. Ask the User what they want to work on this session

## Communication Protocol

- To delegate to L: create a GitHub Issue labeled `agent:local`, full context in body, then POST a ping to ntfy: `{"v":1,"from":"cloud","type":"new-task","ref":"issue:N","ts":"..."}`
- To reply to L: comment on the relevant issue/PR, then ping
- To update durable state: push to docs/STATUS.md, commit with conventional commit format
- To surface something to the User: create an Issue labeled `user:input-needed` and tell the User in chat

## What You Must NOT Do

- Do not assume memory between sessions — everything lives in the repo
- Do not touch repos other than ulp-bridge without explicit User direction
- Do not store the PAT anywhere outside this prompt
- Do not skip the audit log when sending pings

## Conventions

- Branch naming: `task-NNN-slug`
- Commit format: `feat|fix|docs|chore(scope): subject`
- Issue titles: `[TASK-NNN] Subject`
- PR titles: same as the issue they close
```

The User will copy this entire document, paste the PAT and topic into the marked spots, and save it as their personal "boot P" template. Every time they want a session with P, they paste the whole thing into chat.

Acceptance criteria:
- [ ] Cold-boot prompt is self-contained (P can fully rehydrate from it alone)
- [ ] PAT and ntfy topic fields are clearly marked for Qwen to fill in
- [ ] Committed to `docs/COLD_BOOT_PROMPT.md` in the bridge repo

### Task 7 — Bootstrap ping

Once Tasks 1–6 are done:

1. Commit everything to `main`.
2. Write a STATUS.md summarizing what you built, what's pending, what P should do first.
3. Create GitHub Issue #1 in the repo: `[TASK-001] Bridge bootstrap complete — review and onboard P`. Body: summary of what's done, link to COLD_BOOT_PROMPT.md, explicit instruction for the User to copy that file, fill in the PAT and topic, and paste it to P in chat.
4. Run `scripts/ping.sh bootstrap-complete issue:1`.
5. Tell the User out loud (in your opencode session): "Bridge is up. The cold-boot prompt for P is at docs/COLD_BOOT_PROMPT.md in the ulp-bridge repo. Copy it, paste the PAT and topic from `~/.ulp/bridge-cloud.token` and `~/.ulp/bridge-ntfy.topic` into the marked spots, and paste the whole thing into chat with P."

The User will then take that prompt, boot P, and P will pick up from there.

---

## 4. Hosted vs Self-Hosted ntfy — Why Hosted for Day 1

You may prefer self-hosted. Read this before deciding.

**Hosted ntfy.sh:**
- Zero setup, zero maintenance
- No account, no API key, no contract
- The "dependency" is theoretical — there is nothing to maintain, nothing that can bill you, nothing that can leak your data beyond the topic name and ping metadata
- Failure mode: if it dies, we lose real-time. 5-minute GitHub poll catches up. No content is lost because content was never in ntfy.

**Self-hosted ntfy:**
- Needs a public-reachable IP. Your local box can't accept inbound from P's sandbox.
- Option A: VPS ($4–5/mo, or fly.io free tier, or Oracle Cloud Always Free). You provision, you maintain.
- Option B: Cloudflare Tunnel exposing ntfy on your local box. Reintroduces tunnel fragility.
- Option C: A small always-on machine on your LAN with port forwarding. Worse than A and B.

For the User (creative, not technical), asking you to maintain a VPS or tunnel is recurring invisible debt. **My strong recommendation: hosted for now.** The protocol is designed so ntfy is a swappable config value — if we ever migrate to self-hosted, only `~/.ulp/bridge-ntfy.topic` (or a new endpoint URL field we add) changes. Code stays the same.

**If you disagree and want self-hosted from day 1:** that's fine, document your reasoning in `docs/NTFY.md`, set up the VPS or tunnel, change the endpoint in the watcher and publisher scripts, and proceed. Just note that this is a 30-minute vs 5-minute tradeoff for Day 1.

---

## 5. PROTOCOL.md — Draft for You to Refine

Save this as `PROTOCOL.md` in the repo root. Refine as you see fit — you own protocol enforcement.

```markdown
# ULP Bridge Protocol

## Roles
- **U** (User): Creative direction, decisions, HIL. Not technical.
- **L** (Local, Qwen via opencode): File writes, protocol enforcement, local exec.
- **P** (Project Lead, cloud agent): Planning, delegation, review, documentation.

## State

The GitHub repo is the single source of truth. Nothing is real unless it's in the repo.
ntfy is the wake-up channel only — pings carry no content, just references.

## Communication

### P → L (delegation)
1. P creates GitHub Issue labeled `agent:local`, body contains full context
2. P commits task spec to `docs/tasks/TASK-NNN.md` and references it in the issue
3. P POSTs ping: `{"v":1,"from":"cloud","type":"new-task","ref":"issue:N",...}`
4. L's watcher invokes opencode with the issue URL as input

### L → P (results)
1. L creates a branch `task-NNN-slug`, commits work
2. L pushes, opens PR referencing the issue (`Closes #N`)
3. L comments on the issue with summary: what was done, what's open, what's blocked
4. L POSTs ping: `{"v":1,"from":"local","type":"pr-ready","ref":"pr:M",...}`

### L → P (blocked / question)
1. L comments on the issue with the question, labeled `needs-P`
2. L POSTs ping: `{"v":1,"from":"local","type":"blocked","ref":"issue:N",...}`

### Any → U (HIL needed)
1. Create Issue labeled `user:input-needed`
2. State in plain language what decision is needed, what the options are, what default we'll take if no response in 24h
3. Ping U via... nothing automated. Just tell U in chat next time U is around.

## Branches & Commits
- `main` is always shippable
- Branch per task: `task-NNN-slug`
- Commit format: `type(scope): subject` where type ∈ {feat, fix, docs, chore, refactor, test}
- PRs squash-merged

## Audit
- Every ntfy ping is logged to `docs/audit-log.md` by both sender and receiver
- Every Issue comment is itself an audit entry
- STATUS.md is the running state summary; updated at end of each session

## Failure Modes
- ntfy dies → 5-min GitHub poll fallback catches up. No content lost.
- GitHub lags → real-time pings still arrive via ntfy. Receiver may pull stale state; acceptable for our cadence.
- L's watcher dies → cron restarts it (if cron'd) or U notices nothing's happening and restarts manually. Cursor file prevents replay.
- P's session ends mid-task → next cold-boot rehydrates from STATUS.md + open issues. Mid-task state preserved as a `wip` label on the issue.

## What Lives Where
- `docs/STATUS.md` — running state, updated each session
- `docs/COLD_BOOT_PROMPT.md` — P's rehydration prompt
- `docs/tasks/TASK-NNN.md` — full task specs
- `docs/audit-log.md` — append-only ping log
- `docs/NTFY.md` — ntfy endpoint config (topic, or self-hosted URL)
- `PROTOCOL.md` — this file
- `scripts/watch.sh` — L's subscriber
- `scripts/ping.sh` — L's publisher helper
```

---

## 6. Guardrails — What You Must NOT Do

- Do not start any actual project work in this bootstrap task. Bridge only.
- Do not push to any repo other than `ulp-bridge`.
- Do not commit the PAT or ntfy topic to the repo. They live in `~/.ulp/` locally.
- Do not request broader GitHub scopes than listed in Task 1.
- Do not use `--public` when creating the repo. Private only.
- Do not skip the audit log when sending pings.
- Do not assume P has any memory between sessions. Everything P needs must be in `docs/` or the cold-boot prompt.

---

## 7. When You're Done

Hand back to the User, in plain English:

> "Bridge is up. The repo is at <URL>. The cold-boot prompt for P is at `docs/COLD_BOOT_PROMPT.md`. Open it, paste the PAT from `~/.ulp/bridge-cloud.token` and the topic from `~/.ulp/bridge-ntfy.topic` into the marked spots, copy the whole file, and paste it into your next chat with P. P will take it from there."

Then stop. Don't try to do anything else. P will pick up Task 2 (whatever real work the User wants to start with) on the next cloud session.

---

**End of spec. Questions, push back on architecture, or propose changes via the User before executing.**
