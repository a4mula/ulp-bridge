# ULP Bridge Protocol

> Single source of truth for the ULP communication system.  
> Maintained by L (Local agent). Revised via PR.

---

## 1. Roles

| Role | Entity | Responsibilities |
|---|---|---|
| **U** — User | Human | Creative direction, decisions, human-in-the-loop input |
| **L** — Local | Qwen 35B A3B via opencode | File writes, protocol enforcement, local execution, watcher |
| **P** — Project Lead | Cloud agent | Planning, task decomposition, delegation, review, documentation |

---

## 2. State Model

The GitHub repository (`ulp-bridge`) is the **single source of truth**.  
Everything durable — tasks, status, decisions, code — lives in the repo.

`ntfy.sh` is the **wake-up channel only**. Pings carry no content, only references (`{"ref":"issue:14"}`). If ntfy dies, we lose real-time but nothing is lost; a 5-minute GitHub poll catches up.

---

## 3. Communication Flows

### 3.1 P → L (Delegation)

1. P creates a GitHub Issue labeled `agent:local`
2. Issue body contains full context: task spec, acceptance criteria, references
3. P commits task spec to `docs/tasks/TASK-NNN.md`
4. P POSTs ping to ntfy:
   ```json
   {"v":1,"from":"cloud","type":"new-task","ref":"issue:N","ts":"<iso8601>"}
   ```
5. L's watcher receives ping, reads issue, begins work

### 3.2 L → P (Results Submission)

1. L creates branch `task-NNN-slug`
2. L commits work, pushes, opens PR (`Closes #N`)
3. L comments on the issue with summary: done, open, blocked
4. L POSTs ping:
   ```json
   {"v":1,"from":"local","type":"pr-ready","ref":"pr:M","ts":"<iso8601>"}
   ```

### 3.3 L → P (Blocked / Question)

1. L comments on the issue labeled `needs-P`
2. L POSTs ping:
   ```json
   {"v":1,"from":"local","type":"blocked","ref":"issue:N","ts":"<iso8601>"}
   ```

### 3.4 Any → U (Human Input Needed)

1. Create Issue labeled `user:input-needed`
2. State the decision needed, options, and the default action if no response in 24h
3. Tell U in the next chat session

---

## 4. Branch & Commit Conventions

| Rule | Detail |
|---|---|
| `main` | Always shippable |
| Branch naming | `task-NNN-slug` (e.g., `task-001-setup`) |
| Commit format | `type(scope): subject` where type ∈ {feat, fix, docs, chore, refactor, test} |
| PR merge | Squash-merge |
| Issue titles | `[TASK-NNN] Subject` |
| PR titles | Same as the issue they close |

---

## 5. Audit

- Every ntfy ping is logged to `docs/audit-log.md` by both sender and receiver
- Every issue comment serves as an audit entry
- `docs/STATUS.md` is the running state summary; updated at end of each session
- Cursor file (`~/.ulp/watcher.cursor`) prevents message replay on restart

---

## 6. Failure Modes

| Failure | Impact | Mitigation |
|---|---|---|
| ntfy dies | Lose real-time | 5-min GitHub poll catches up |
| GitHub lags | Pings may reference stale state | Acceptable for our cadence |
| L's watcher dies | Missed pings | Cron restarts; cursor prevents replay |
| P's session ends mid-task | Incomplete work | `wip` label on issue; cold-boot rehydrates from STATUS.md |

---

## 7. File Layout

```
ulp-bridge/
├── PROTOCOL.md              # This file
├── README.md
├── docs/
│   ├── STATUS.md            # Running state summary
│   ├── audit-log.md         # Append-only ping log
│   ├── COLD_BOOT_PROMPT.md  # P's rehydration prompt
│   ├── tasks/
│   │   └── TASK-NNN.md      # Task specs
│   └── NTFY.md              # ntfy endpoint config
├── scripts/
│   ├── watch.py             # L's subscriber (worker)
│   └── ping.sh              # L's publisher helper
└── .gitignore
```
