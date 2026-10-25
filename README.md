> Authored with Claude (Anthropic) as coding agent, under human direction and review.

# ip-beacon

A headless box on DHCP can change address at any time, and without a screen you
then have no way to reach it. ip-beacon fixes that: the box broadcasts its
hostname and current IP on the LAN every few seconds, so any machine on the
network can listen and learn where it went.

## How it works

The sender emits one small JSON datagram to the broadcast address on UDP port
55555:

```json
{"beacon":"ip-beacon","hostname":"<name>","ip":"<primary-ip>","ts":<epoch>}
```

It re-reads its primary outbound IP every cycle, so the announcement tracks DHCP
changes rather than pinning to a stale lease.

## Install

Run the installer on the headless host as root:

```sh
sudo ./install.sh
```

It copies the daemon to /usr/local/bin, installs a systemd unit, and enables the
service so it starts on boot and restarts on failure. If ufw is active, it also
opens 55555/udp.

## Verify

Confirm the service is up, then watch for a beacon:

```sh
systemctl --no-pager --full status ip-beacon.service
timeout 8 python3 listener.py
```

The host receives its own broadcast, so this self-test works on the box alone,
with no second machine.

## Listening

`listener.py` prints one line per host and re-prints only when that host's IP
changes. Run it on whatever machine you watch from:

```sh
python3 listener.py                 # continuous
python3 listener.py --once          # first beacon, then exit
python3 listener.py --once --name my-box
python3 listener.py --once --ip 192.168.1.42
```

`--once` is useful for scripted discovery: it prints the first matching beacon
and exits 0. Combine `--name` and/or `--ip` to accept only beacons from a
particular host, ignoring unrelated cross chatter on the LAN. Ctrl-C before a
match exits 1.

Run it natively on the host, though, not inside WSL2. In mirrored networking mode
a bound socket never receives externally-originated LAN broadcasts, so the
listener binds cleanly and then sits silent. On Windows that means the Windows
Python, not the one in your WSL distro.

The script is stdlib-only and needs no install. A plain `nc -ul 55555` works too,
if you would rather not run it.

## Configuration

Both scripts read these from the environment; the systemd unit sets them with
`Environment=` lines.

| Variable | Default | Meaning |
|---|---|---|
| `BEACON_PORT` | `55555` | UDP port to broadcast and listen on |
| `BEACON_INTERVAL` | `5` | Seconds between broadcasts (sender) |
| `BEACON_ADDR` | `255.255.255.255` | Destination broadcast address (sender) |

To change the port or interval after install, edit the `Environment=` lines in
/etc/systemd/system/ip-beacon.service, then `systemctl daemon-reload &&
systemctl restart ip-beacon`.

## License

Public domain, under the Unlicense. See UNLICENSE.
