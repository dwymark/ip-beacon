#!/usr/bin/env python3
"""Listen for ip-beacon broadcasts on the LAN and print them (one line per host,
re-printed only when a host's IP changes). Run on your laptop:

    python3 listener.py

Stop with Ctrl-C. Stdlib only; works on macOS, Linux, and Windows. Run it
natively on the host, not inside WSL2: in mirrored networking mode a bound
socket does not receive the LAN's broadcasts, so the listener stays silent.

Plain alternatives without this script:
    Linux:  nc -ul 55555
    macOS:  nc -ul 55555          (BSD nc; press Ctrl-C to stop)
"""
import json
import os
import socket
import sys

PORT = int(os.environ.get("BEACON_PORT", "55555"))


def main() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))
    print(f"listening for ip-beacon on udp/{PORT} ... Ctrl-C to stop")

    last: dict[str, str] = {}
    while True:
        data, addr = sock.recvfrom(65535)
        try:
            m = json.loads(data.decode("utf-8"))
            if m.get("beacon") != "ip-beacon":
                continue
            host, ip = m.get("hostname", "?"), m.get("ip", "?")
            if last.get(host) != ip:
                last[host] = ip
                print(f"{host:<24} {ip:<15} (datagram from {addr[0]})")
        except (ValueError, UnicodeDecodeError):
            print(f"{addr[0]}: non-beacon datagram: {data!r}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
