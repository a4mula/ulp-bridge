#!/usr/bin/env python3
"""
ULP Bridge Watcher — ntfy subscriber for L (Local agent).

Reads pings from ntfy.sh, logs to audit log, and invokes opencode
with the task context from GitHub issues.

Usage:
    python3 scripts/watch.py [--foreground]
"""

import json
import sys
import time
import signal
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HOME = Path.home()
CONFIG_DIR = HOME / ".ulp"
TOPIC_FILE = CONFIG_DIR / "bridge-ntfy.topic"
CURSOR_FILE = CONFIG_DIR / "watcher.cursor"
AUDIT_LOG = Path(__file__).resolve().parent.parent / "docs" / "audit-log.md"

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


def invoke_opencode(ref: str, message: str) -> None:
    """Invoke opencode with the task context."""
    # Try to find opencode in common locations
    opencode_paths = [
        Path("/usr/local/bin/opencode"),
        Path("/usr/bin/opencode"),
        Path.home() / "bin/opencode",
    ]
    
    opencode_bin = None
    for p in opencode_paths:
        if p.exists():
            opencode_bin = p
            break
    
    if not opencode_bin:
        # Try via PATH
        result = subprocess.run(["which", "opencode"], capture_output=True, text=True)
        if result.returncode == 0:
            opencode_bin = Path(result.stdout.strip())
        else:
            log.warning("opencode binary not found — skipping invocation")
            return
    
    prompt = f"P posted an update to {ref} — read it, act, report.\n\nMessage: {message}"
    
    log.info(f"Invoking opencode with ref={ref}")
    # In a real deployment, this would use opencode's API or CLI
    # For now, we log the invocation
    log.info(f"opencode prompt: {prompt[:200]}...")

# ---------------------------------------------------------------------------
# ntfy stream processing
# ---------------------------------------------------------------------------


def process_message(event: dict) -> None:
    """Process a single ntfy event."""
    raw = json.dumps(event)
    ts = event.get("time", "")
    
    # Convert Unix timestamp to ISO8601
    if ts:
        ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Save cursor for restart safety
    save_cursor(ts_iso)
    
    msg_type = event.get("event", "message")
    data = event.get("data", "")
    
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
        invoke_opencode(ref, message)
        
        log.info(f"Processed cloud message: type={msg_type_field}, ref={ref}")
    
    else:
        log.debug(f"Unknown 'from' field: {from_field}")

# ---------------------------------------------------------------------------
# ntfy stream connection
# ---------------------------------------------------------------------------


def connect_stream(topic: str, since: Optional[str] = None) -> None:
    """Connect to ntfy stream and process messages."""
    import urllib.request
    
    url = f"https://ntfy.sh/{topic}/stream?since=all"
    if since:
        url = f"https://ntty.sh/{topic}/stream?since={since}"
    
    log.info(f"Connecting to ntfy stream: {url}")
    
    while True:
        try:
            req = urllib.request.Request(url)
            # 60s read timeout, will reconnect on timeout
            with urllib.request.urlopen(req, timeout=60) as response:
                log.info("Connected to ntfy stream")
                
                # Read line by line (ndjson)
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    
                    try:
                        event = json.loads(line)
                        process_message(event)
                    except json.JSONDecodeError as e:
                        log.warning(f"JSON parse error: {e}")
                        
        except urllib.error.HTTPError as e:
            log.error(f"HTTP error: {e.code} {e.reason}")
            time.sleep(5)
        except Exception as e:
            log.error(f"Connection error: {e}")
            time.sleep(5)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    """Main entry point."""
    # Handle signals for graceful shutdown
    def shutdown(signum, frame):
        log.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    topic = get_topic()
    cursor = get_cursor()
    
    log.info(f"ULP Bridge Watcher starting")
    log.info(f"Topic: {topic}")
    log.info(f"Cursor: {cursor or 'none'}")
    
    # Connect to ntfy stream
    connect_stream(topic, since=cursor)


if __name__ == "__main__":
    main()
