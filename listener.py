#!/usr/bin/env python3
"""Listen for ip-beacon broadcasts on the LAN.

Continuous mode (default): prints one line per host, re-printed only when
that host's IP changes. Stop with Ctrl-C.

One-shot mode (--once): prints the first received beacon and exits with
status 0. Combine --name and/or --ip to accept only beacons from a
particular host, ignoring unrelated cross chatter on the LAN. Ctrl-C
before a match exits with status 1.

    python3 listener.py                 # continuous
    python3 listener.py --once          # first beacon, then exit
    python3 listener.py --once --name my-box
    python3 listener.py --once --ip 192.168.1.42

Stdlib only; works on macOS, Linux, and Windows. Run it natively on the
host, not inside WSL2: in mirrored networking mode a bound socket does
not receive the LAN's broadcasts, so the listener stays silent.

Plain alternatives without this script:
    Linux:  nc -ul 55555
    macOS:  nc -ul 55555          (BSD nc; press Ctrl-C to stop)
"""
import argparse
import json
import os
import socket
import sys

PORT = int(os.environ.get("BEACON_PORT", "55555"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="listen for ip-beacon datagrams")
    p.add_argument("--once", action="store_true",
                   help="print the first received beacon and exit 0; "
                        "Ctrl-C before a match exits 1")
    p.add_argument("--name",
                   help="only accept beacons with this hostname (exact match)")
    p.add_argument("--ip",
                   help="only accept beacons reporting this IP (exact match)")
    return p.parse_args()


def main(args: argparse.Namespace) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))

    last: dict[str, str] = {}
    if not args.once:
        print(f"listening for ip-beacon on udp/{PORT} ... Ctrl-C to stop", flush=True)

    while True:
        data, addr = sock.recvfrom(65535)
        try:
            m = json.loads(data.decode("utf-8"))
            if not isinstance(m, dict):
                raise ValueError("not a JSON object")
        except (ValueError, UnicodeDecodeError):
            if not args.once:
                print(f"{addr[0]}: non-beacon datagram: {data!r}", flush=True)
            continue
        if m.get("beacon") != "ip-beacon":
            continue
        host, ip = m.get("hostname", "?"), m.get("ip", "?")
        if args.name is not None and host != args.name:
            continue
        if args.ip is not None and ip != args.ip:
            continue
        if args.once:
            print(f"{host:<24} {ip:<15} (datagram from {addr[0]})", flush=True)
            return 0
        if last.get(host) != ip:
            last[host] = ip
            print(f"{host:<24} {ip:<15} (datagram from {addr[0]})", flush=True)


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(main(args))
    except KeyboardInterrupt:
        print()
        sys.exit(1 if args.once else 0)
