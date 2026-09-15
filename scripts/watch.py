#!/usr/bin/env python3
"""
ULP Bridge Watcher — ntfy subscriber for L (Local agent).

Reads pings from ntfy.sh, logs to audit log, and invokes opencode
with the task context from GitHub issues.

Usage:
    python3 scripts/watch.py [--foreground] [--dry-run]
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HOME = Path.home()
CONFIG_DIR = HOME / ".ulp"
TOPIC_FILE = CONFIG_DIR / "bridge-ntfy.topic"
CURSOR_FILE = CONFIG_DIR / "watcher.cursor"
AUDIT_LOG = Path(__file__).resolve().parent.parent / "docs" / "audit-log.md"

NTFY_URL = "https://ntfy.sh"

# opencode invocation timeout (seconds). Local models doing agentic runs are
# slow — 120s was empirically far too short. Override at runtime with the
# ULP_OC_TIMEOUT environment variable.
OC_TIMEOUT = int(os.environ.get("ULP_OC_TIMEOUT", "900"))

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger("ulp-watcher")

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text().strip()


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def get_topic() -> str:
    topic = _read_file(TOPIC_FILE)
    if not topic:
        log.error(f"Topic not found at {TOPIC_FILE}")
        sys.exit(1)
    return topic


def get_cursor() -> Optional[str]:
    """Get the last processed message timestamp for restart safety."""
    return _read_file(CURSOR_FILE)


def save_cursor(ts: str) -> None:
    """Persist the last processed message timestamp."""
    _write_file(CURSOR_FILE, ts)

# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def append_audit_log(msg: str, raw: str) -> None:
    """Append an entry to the audit log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"\n## {ts}\n\n- **{msg}**\n  ```\n{raw}\n  ```\n"

    if AUDIT_LOG.exists():
        content = AUDIT_LOG.read_text()
        # Insert before the last section if STATUS exists
        AUDIT_LOG.write_text(content + entry)
    else:
        AUDIT_LOG.write_text(f"# Audit Log\n\n{entry}")

# ---------------------------------------------------------------------------
# Opencode invocation
# ---------------------------------------------------------------------------


def _resolve_opencode_bin() -> Optional[Path]:
    """Resolve the opencode binary path."""
    opencode_paths = [
        Path("/usr/local/bin/opencode"),
        Path("/usr/bin/opencode"),
        Path.home() / "bin/opencode",
    ]

    for p in opencode_paths:
        if p.exists():
            return p

    result = subprocess.run(["which", "opencode"], capture_output=True, text=True)
    if result.returncode == 0:
        return Path(result.stdout.strip())

    return None


def _post_blocked_ping(ref: str) -> None:
    """POST a blocked ping via ping.sh.

    Refs pass through unchanged (pr:7, commit:abc123, ...). Only a bare
    numeric ref is assumed to be an issue id and gets the 'issue:' prefix.
    (The old rule prefixed EVERYTHING lacking 'issue:', which both produced
    'issue:issue:14' and mangled 'commit:...' refs into 'issue:commit:...'.)
    """
    ping_script = Path(__file__).resolve().parent / "ping.sh"
    if not ping_script.exists():
        log.error(f"ping.sh not found at {ping_script}")
        return

    if ref.isdigit():
        ref = f"issue:{ref}"

    try:
        subprocess.run(
            ["bash", str(ping_script), "blocked", ref],
            capture_output=True,
            text=True,
            timeout=30,
        )
        log.info(f"POSTed blocked ping for {ref}")
    except Exception as exc:
        log.error(f"Failed to POST blocked ping for {ref}: {exc}")


def invoke_opencode(ref: str, message: str, dry_run: bool = False) -> bool:
    """Invoke opencode with the task context.

    Returns True on success, False on failure.

    Lessons baked in after the 2026-09-15 silent-hang incident:
    - opencode stdout/stderr are streamed live into the watcher log with an
      '[oc:*]' prefix — capture_output() hid everything and a healthy-looking
      invocation was indistinguishable from a dead one.
    - The child runs in its own process group (start_new_session) and the
      timeout kills the WHOLE group. Killing only the opencode parent can
      leave tool-children holding our stdout/stderr pipes open, and then
      subprocess.run() never returns from its post-kill communicate() — the
      watcher wedges silently, no timeout log, no blocked ping.
    - stdin is /dev/null: nothing waits on a human.
    - Timeout defaults to 900s (local-model agentic runs are slow); override
      with ULP_OC_TIMEOUT=<seconds>.
    """
    if dry_run:
        log.info(f"[DRY-RUN] Would invoke opencode with ref={ref}")
        log.info(f"[DRY-RUN] opencode prompt: {message[:200]}...")
        return True

    opencode_bin = _resolve_opencode_bin()
    if not opencode_bin:
        log.warning("opencode binary not found — skipping invocation")
        _post_blocked_ping(ref)
        return False

    prompt = f"P posted an update to {ref} — read it, act, report.\n\nMessage: {message}"

    log.info(f"Invoking opencode with ref={ref}")
    log.info(
        f"opencode: bin={opencode_bin} timeout={OC_TIMEOUT}s "
        f"cwd={Path.cwd()} prompt_chars={len(prompt)}"
    )

    try:
        proc = subprocess.Popen(
            [str(opencode_bin), "run", prompt],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,  # own process group — see docstring
        )
    except Exception as exc:
        log.error(f"opencode failed to start: {exc}")
        _post_blocked_ping(ref)
        return False

    def _pump(stream, tag: str) -> None:
        try:
            for line in stream:
                log.info(f"[oc:{tag}] {line.rstrip()}")
        except Exception as exc:
            log.warning(f"[oc:{tag}] pump error: {exc}")
        finally:
            try:
                stream.close()
            except Exception:
                pass

    threads = [
        threading.Thread(target=_pump, args=(proc.stdout, "out"), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, "err"), daemon=True),
    ]
    for t in threads:
        t.start()

    def _kill_group() -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError) as exc:
            log.warning(f"killpg: {exc}")

    started = time.monotonic()
    heartbeat = 0
    timed_out = False
    try:
        while proc.poll() is None:
            time.sleep(1)
            elapsed = time.monotonic() - started
            if elapsed >= (heartbeat + 1) * 60 and proc.poll() is None:
                heartbeat += 1
                log.info(f"opencode still running: {int(elapsed)}s elapsed")
            if elapsed >= OC_TIMEOUT:
                timed_out = True
                log.error(
                    f"opencode exceeded {OC_TIMEOUT}s — killing process group "
                    f"(set ULP_OC_TIMEOUT if this task needs longer)"
                )
                _kill_group()
                break
    except BaseException:
        # Covers SystemExit from the SIGINT/SIGTERM handler and
        # KeyboardInterrupt — don't leave orphaned opencode trees behind.
        log.error("watcher exiting while opencode was running — killing process group")
        _kill_group()
        raise

    returncode = proc.wait()
    for t in threads:
        t.join(timeout=10)
    elapsed = int(time.monotonic() - started)

    if timed_out or returncode != 0:
        log.error(
            f"opencode {'timed out' if timed_out else f'exited rc={returncode}'} "
            f"after {elapsed}s — see [oc:*] lines above for its output"
        )
        _post_blocked_ping(ref)
        return False

    log.info(f"opencode finished OK (rc=0, {elapsed}s)")
    return True

# ---------------------------------------------------------------------------
# ntfy stream processing
# ---------------------------------------------------------------------------


def process_message(event: dict, dry_run: bool = False) -> None:
    """Process a single ntfy event."""
    raw = json.dumps(event)
    ts = event.get("time", "")

    # Harden: coerce time to a float/str before converting
    ts_iso = ""
    ts_unix = ""
    if ts:
        try:
            ts_num = float(ts)
            ts_iso = datetime.fromtimestamp(ts_num, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ts_unix = str(int(ts_num))
        except (ValueError, OSError, OverflowError) as exc:
            log.warning(f"Malformed time value '{ts}': {exc}; using current time")
            ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ts_unix = str(int(datetime.now(timezone.utc).timestamp()))
    else:
        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_unix = str(int(datetime.now(timezone.utc).timestamp()))

    # Save cursor for restart safety.
    # ntfy 'since' accepts unix seconds / durations / message ids — NOT ISO
    # strings (ISO cursor → HTTP 400 on reconnect), so store unix seconds.
    save_cursor(ts_unix)

    msg_type = event.get("event", "message")
    # ntfy /json stream carries the published body in 'message' (not 'data')
    data = event.get("message") or event.get("data") or ""

    try:
        payload = json.loads(data) if data else {}
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON data: {data[:100]}")
        payload = {}

    from_field = payload.get("from", "")

    # Ignore our own pings
    if from_field == "local":
        log.debug(f"Ignoring local ping: {payload.get('type')}")
        return

    # Process cloud messages
    if from_field == "cloud":
        msg_type_field = payload.get("type", "unknown")
        ref = payload.get("ref", "unknown")

        # Log to audit
        append_audit_log(f"Cloud ping: {msg_type_field} → {ref}", raw)

        # Invoke opencode
        message = f"Cloud ping received: {msg_type_field} with ref {ref}"
        invoke_opencode(ref, message, dry_run=dry_run)

        log.info(f"Processed cloud message: type={msg_type_field}, ref={ref}")

    else:
        log.debug(f"Unknown 'from' field: {from_field}")

# ---------------------------------------------------------------------------
# ntfy stream connection
# ---------------------------------------------------------------------------


def _build_url(topic: str, since: Optional[str] = None) -> str:
    """Build the ntfy stream URL using the canonical NTFY_URL constant.

    ntfy's ndjson subscribe endpoint is /json (there is no /stream path —
    it returns 404); ping payloads arrive in the 'message' field.
    """
    if since:
        return f"{NTFY_URL}/{topic}/json?since={since}"
    return f"{NTFY_URL}/{topic}/json?since=all"


def connect_stream(topic: str, since: Optional[str] = None, dry_run: bool = False) -> None:
    """Connect to ntfy stream and process messages."""
    url = _build_url(topic, since)
    log.info(f"Connecting to ntfy stream: {url}")

    reconnect_delay = 5
    max_reconnect_delay = 60

    while True:
        try:
            req = urllib.request.Request(url)
            # 60s read timeout, will reconnect on timeout
            with urllib.request.urlopen(req, timeout=60) as response:
                log.info("Connected to ntfy stream")
                reconnect_delay = 5  # reset on successful connect

                # Read line by line (ndjson)
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        process_message(event, dry_run=dry_run)
                    except json.JSONDecodeError as e:
                        log.warning(f"JSON parse error (skipping line): {e}")
                    except Exception as e:
                        log.error(f"Error processing event: {e}; skipping")

        except urllib.error.HTTPError as e:
            log.error(f"HTTP error: {e.code} {e.reason}")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
        except Exception as e:
            log.error(f"Connection error: {e}")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _valid_since(cursor: Optional[str]) -> Optional[str]:
    """Sanitize the stored cursor into a value ntfy's 'since' accepts.

    ntfy accepts unix seconds, durations (e.g. 30m), message ids, or 'all' —
    NOT ISO strings (HTTP 400). Old cursors stored as ISO are converted to
    unix seconds; garbage is dropped (restart from 'all').
    """
    if not cursor:
        return None
    if cursor.isdigit():
        return cursor
    try:
        dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        converted = str(int(dt.timestamp()))
        log.info(f"Converted legacy ISO cursor {cursor} → unix {converted}")
        return converted
    except ValueError:
        log.warning(f"Ignoring unparseable cursor '{cursor}' — starting from 'all'")
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ULP Bridge Watcher")
    parser.add_argument("--dry-run", action="store_true", help="Log events without invoking opencode")
    parser.add_argument("--foreground", action="store_true", help="Run in foreground (default)")
    args = parser.parse_args()

    # Handle signals for graceful shutdown
    def shutdown(signum, frame):
        log.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    topic = get_topic()
    cursor = get_cursor()
    since = _valid_since(cursor)

    log.info(f"ULP Bridge Watcher starting")
    log.info(f"Topic: {topic}")
    log.info(f"Cursor: {cursor or 'none'}")
    if args.dry_run:
        log.info("Running in DRY-RUN mode — no opencode invocations will occur")

    # Connect to ntfy stream
    connect_stream(topic, since=since, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
