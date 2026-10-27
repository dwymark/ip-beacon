#!/usr/bin/env python3
"""Listen for ip-beacon broadcasts on the LAN.

Continuous mode (default): prints one line per host, re-printed only when
that host's IP changes. Stop with Ctrl-C.

One-shot mode (--once): prints the first received beacon and exits with
status 0. Combine --name and/or --ip to accept only beacons from a
particular host, ignoring unrelated cross chatter on the LAN. Ctrl-C
before a match exits with status 1.

DNS mode (--hosts-dir DIR --map HOST=NAME[,HOST=NAME...]): continuous mode
that also keeps DIR/ip-beacon.hosts, a hosts file for dnsmasq's --hostsdir.
It answers each NAME with the address HOST's beacons arrive from, which is
the datagram's source rather than the address the payload reports, until
--expire seconds pass without one. HOST matches case-insensitively. It
prints beacons as continuous mode does, but not non-beacon datagrams, which
would fill a service's journal.

    python3 listener.py                 # continuous
    python3 listener.py --once          # first beacon, then exit
    python3 listener.py --once --name my-box
    python3 listener.py --once --ip 192.168.1.42
    python3 listener.py --hosts-dir /var/lib/ip-beacon-dns --map my-box=box.example.com

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
import time

PORT = int(os.environ.get("BEACON_PORT", "55555"))
HOSTS_FILE = "ip-beacon.hosts"


def parse_map(text: str) -> dict[str, str]:
    names = {}
    for item in filter(None, text.split(",")):
        host, sep, name = item.partition("=")
        if not (sep and host and name):
            raise argparse.ArgumentTypeError(f"expected HOST=NAME, got {item!r}")
        names[host.lower()] = name
    return names


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="listen for ip-beacon datagrams")
    p.add_argument("--once", action="store_true",
                   help="print the first received beacon and exit 0; "
                        "Ctrl-C before a match exits 1")
    p.add_argument("--name",
                   help="only accept beacons with this hostname (exact match)")
    p.add_argument("--ip",
                   help="only accept beacons reporting this IP (exact match)")
    p.add_argument("--hosts-dir",
                   help=f"keep DIR/{HOSTS_FILE} for dnsmasq's --hostsdir")
    p.add_argument("--map", type=parse_map, default={},
                   help="HOST=NAME[,HOST=NAME...]: the names --hosts-dir answers")
    p.add_argument("--expire", type=float, default=120,
                   help="seconds a name outlives its host's last beacon (default 120)")
    args = p.parse_args()
    if args.hosts_dir and not args.map:
        p.error("--hosts-dir needs --map")
    if args.hosts_dir and args.once:
        p.error("--hosts-dir runs continuously; drop --once")
    return args


class Records:
    """The hosts file under a dnsmasq --hostsdir: each mapped name, while its host's beacons keep arriving."""

    def __init__(self, directory: str, names: dict[str, str], expire: float):
        self.path = os.path.join(directory, HOSTS_FILE)
        # dnsmasq ignores dotfiles in a hostsdir, so the partial file is never read.
        self.partial = os.path.join(directory, "." + HOSTS_FILE)
        self.names, self.expire = names, expire
        self.seen: dict[str, tuple[str, float]] = {}
        self.written: str | None = None
        self.write()

    def beacon(self, host: str, address: str) -> None:
        name = self.names.get(host.lower())
        if name:
            self.seen[name] = (address, time.monotonic())

    def write(self) -> None:
        """Drop expired names and rewrite the file when its contents change."""
        now = time.monotonic()
        self.seen = {n: s for n, s in self.seen.items() if now - s[1] < self.expire}
        text = "".join(f"{address} {name}\n" for name, (address, _) in sorted(self.seen.items()))
        if text == self.written:
            return
        with open(self.partial, "w") as f:
            f.write(text)
        os.replace(self.partial, self.path)
        self.written = text


def main(args: argparse.Namespace) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", PORT))
    records = Records(args.hosts_dir, args.map, args.expire) if args.hosts_dir else None
    if records:
        # Wake up without datagrams too, so a silent host's name still expires.
        sock.settimeout(5)

    last: dict[str, str] = {}
    if not args.once:
        print(f"listening for ip-beacon on udp/{PORT} ... Ctrl-C to stop", flush=True)

    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except TimeoutError:
            data = None
        if records:
            records.write()
        if data is None:
            continue
        try:
            m = json.loads(data.decode("utf-8"))
            if not isinstance(m, dict):
                raise ValueError("not a JSON object")
        except (ValueError, UnicodeDecodeError):
            if not (args.once or records):
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
        if records:
            records.beacon(str(host), addr[0])
            records.write()
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
