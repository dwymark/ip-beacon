#!/usr/bin/env python3
"""ip-beacon: periodically broadcast this host's name and primary IP over UDP.

Intended for a headless box on DHCP so another machine on the LAN can discover
its current address without a screen. Emits a single-line JSON datagram to the
limited broadcast address (255.255.255.255) on a configurable port.

Stdlib only. Configuration via environment variables (set in the systemd unit):
  BEACON_PORT      UDP port to broadcast on            (default 55555)
  BEACON_INTERVAL  seconds between broadcasts          (default 5)
  BEACON_ADDR      destination broadcast address       (default 255.255.255.255)
"""
import json
import os
import socket
import sys
import time

PORT = int(os.environ.get("BEACON_PORT", "55555"))
INTERVAL = float(os.environ.get("BEACON_INTERVAL", "5"))
BROADCAST_ADDR = os.environ.get("BEACON_ADDR", "255.255.255.255")


def primary_ip() -> str:
    """Best-effort primary outbound IPv4 address.

    Opens a UDP socket and 'connects' it to an unrouted TEST-NET-1 address.
    No packet is actually sent; the kernel just picks the source address it
    would use to reach that destination, which is the primary interface IP.
    Survives DHCP changes because it is re-evaluated every cycle.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1 (RFC 5737), guaranteed unrouted
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()


def main() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    hostname = socket.gethostname()

    while True:
        payload = {
            "beacon": "ip-beacon",
            "hostname": hostname,
            "ip": primary_ip(),
            "ts": int(time.time()),
        }
        try:
            sock.sendto(json.dumps(payload).encode("utf-8"), (BROADCAST_ADDR, PORT))
        except OSError:
            # Network may be momentarily down (link flap, DHCP renew). Don't die;
            # just skip this cycle and try again. systemd Restart=always is the
            # backstop for anything fatal.
            pass
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
