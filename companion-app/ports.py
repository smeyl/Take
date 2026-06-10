"""Startup port-conflict detection.

Flask servers launched on daemon threads die silently when their port is
taken — the app looks alive but the service is missing. Checking up front
turns that into a clear error before anything starts.
"""
import socket
import sys


def _is_free(port, proto):
    kind = socket.SOCK_STREAM if proto == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, kind) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def ensure_free(specs):
    """specs: list of (port, "tcp"|"udp", human-readable name).
    Prints every conflict and exits if any port is taken."""
    conflicts = [(p, proto, name) for p, proto, name in specs
                 if not _is_free(p, proto)]
    if not conflicts:
        return
    print("Port conflict — cannot start:", file=sys.stderr)
    for port, proto, name in conflicts:
        print(f"  {proto.upper()} {port} ({name}) is already in use", file=sys.stderr)
    print("Close the other process (try: lsof -i :PORT) and run again.", file=sys.stderr)
    sys.exit(1)
