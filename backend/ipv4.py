"""Make Take's HTTP connections (requests / urllib3) resolve addresses as IPv4.

Take connects to IPv4 addresses only — the LAN and Tailscale's 100.x. On an
IPv6-only network with NAT64 (an iPhone hotspot, some mobile and home ISPs),
macOS's getaddrinfo rewrites an IPv4 literal into a synthesized NAT64 IPv6
address; the connection then leaves through the carrier instead of the
Tailscale interface and times out (measured: 100.x reachable in ~60 ms over a
raw IPv4 socket, while requests timed out every time). Import this module
first in every Take process.
"""
import socket

import urllib3.util.connection

urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
