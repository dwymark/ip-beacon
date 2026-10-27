#!/usr/bin/env python3
"""ip-beacon: periodically broadcast this host's name and primary IP over UDP.

Intended for a headless box on DHCP so another machine on the LAN can discover
its current address without a screen. Emits a single-line JSON datagram to the
broadcast address of every interface that is up and has one, re-read each
cycle, on a configurable port. The limited broadcast address (255.255.255.255)
would follow the default route, which a VPN takes off the LAN.

Stdlib only. On Windows, which has no fcntl to read interfaces with, set
BEACON_ADDR; install-windows.ps1 does. Configuration via environment variables
(set in the systemd unit):
  BEACON_PORT      UDP port to broadcast on            (default 55555)
  BEACON_INTERVAL  seconds between broadcasts          (default 5)
  BEACON_ADDR      one destination address instead     (default: every interface's)
"""
import json
import os
import socket
import struct
import sys
import time

try:
    import fcntl
except ImportError:  # Windows, where BEACON_ADDR names the destination
    fcntl = None

PORT = int(os.environ.get("BEACON_PORT", "55555"))
INTERVAL = float(os.environ.get("BEACON_INTERVAL", "5"))
BROADCAST_ADDR = os.environ.get("BEACON_ADDR", "")

SIOCGIFFLAGS, SIOCGIFADDR, SIOCGIFBRDADDR = 0x8913, 0x8915, 0x8919
IFF_UP, IFF_BROADCAST, IFF_LOOPBACK, IFF_RUNNING = 0x1, 0x2, 0x8, 0x40


def broadcast_addrs(sock: socket.socket) -> list[str]:
    """The broadcast address of each interface that is up, has a carrier and is not the loopback (Linux).

    A /32, such as a VPN's or Tailscale's interface, reports its own address as its broadcast address and is skipped.
    """
    if fcntl is None:
        return ["255.255.255.255"]
    found = []
    # /sys rather than socket.if_nameindex(), whose netlink socket the unit's RestrictAddressFamilies refuses.
    try:
        names = os.listdir("/sys/class/net")
    except OSError:
        names = []
    for name in names:
        request = struct.pack("256s", name.encode()[:15])
        try:
            flags = struct.unpack("H", fcntl.ioctl(sock, SIOCGIFFLAGS, request)[16:18])[0]
            if flags & (IFF_UP | IFF_BROADCAST | IFF_RUNNING | IFF_LOOPBACK) != IFF_UP | IFF_BROADCAST | IFF_RUNNING:
                continue
            own = fcntl.ioctl(sock, SIOCGIFADDR, request)[20:24]
            broadcast = fcntl.ioctl(sock, SIOCGIFBRDADDR, request)[20:24]
            if broadcast != own:
                found.append(socket.inet_ntoa(broadcast))
        except OSError:
            continue  # no IPv4 address on this interface
    return found or ["255.255.255.255"]


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
        for address in [BROADCAST_ADDR] if BROADCAST_ADDR else broadcast_addrs(sock):
            try:
                sock.sendto(json.dumps(payload).encode("utf-8"), (address, PORT))
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
