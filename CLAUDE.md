# ip-beacon

A headless host broadcasts its hostname and primary IP over UDP so another
machine on the LAN can discover it without a screen, even as DHCP moves its
address. `ip-beacon.py` is the sender daemon; `listener.py` is the receiver.

## Layout

- `ip-beacon.py` — sender daemon, stdlib only. Every `BEACON_INTERVAL` seconds
  it re-reads the primary outbound IPv4 and broadcasts one JSON datagram to
  `BEACON_ADDR` on `BEACON_PORT`:
  `{"beacon":"ip-beacon","hostname":...,"ip":...,"ts":...}`.
- `listener.py` — receiver, stdlib only. Binds `BEACON_PORT` and prints one line
  per host, re-printed only when that host's IP changes. `--once` (with optional
  `--name`/`--ip` filters) prints the first matching beacon and exits; useful for
  scripted discovery where you want to ignore cross chatter. `--hosts-dir` with
  `--map HOST=NAME` keeps a dnsmasq hosts file answering NAME with the source
  address of HOST's beacons, until `--expire` seconds (default 120) pass without
  one.
- `ip-beacon-dns.service` — systemd unit for that DNS mode, as the static
  `ip-beacon` user, writing `/var/lib/ip-beacon-dns`, which dnsmasq reads.
- `ip-beacon.service` — systemd unit for the sender. Runs as an ephemeral
  `DynamicUser`, starts on boot, restarts on failure.
- `install.sh` — installs the daemon and unit, enables the service, and opens
  `55555/udp` when `ufw` is active. Needs root. Run locally with no arguments
  (`sudo ./install.sh`), or point it at a remote Linux host with
  `./install.sh [user@]<ip>`, which copies the repo over ssh/scp and runs the
  installer there via `sudo` (no root needed locally in that mode). With
  `--dns HOST=NAME --upstream IP[,IP]` it also installs dnsmasq and the DNS unit;
  the upstream servers are required, since the host's own resolver may forward
  back to it.

## Configuration

Both scripts read these from the environment; the unit sets them via
`Environment=` lines.

- `BEACON_PORT` — UDP port. Default `55555`.
- `BEACON_INTERVAL` — seconds between broadcasts (sender only). Default `5`.
- `BEACON_ADDR` — destination broadcast address (sender only). Default
  `255.255.255.255`.

## Install and verify (sender host)

```sh
sudo ./install.sh                       # locally, or:
./install.sh user@sender-host           # remotely, over ssh

systemctl --no-pager --full status ip-beacon.service   # expect: active (running)
timeout 8 python3 listener.py                          # expect a beacon line within ~6s
python3 listener.py --once --name <hostname>           # one-shot, filter by name
python3 listener.py --once --ip <ip>                   # one-shot, filter by IP
```

The sender receives its own broadcast, so the listener self-test needs no second
machine. Run the status/listener checks on the sender host itself (ssh in, if
installed remotely).

## Running the listener

Run `listener.py` natively on the receiving host. Do not run it inside WSL2: in
mirrored networking mode a bound socket does not receive externally-originated
LAN broadcasts, so the listener binds but hears nothing. On Windows, run it under
the Windows Python, not the WSL one.

## Conventions

The tracked tree is present truth; git history is the worklog. Keep comments and
docs describing the current system only, delete dead code rather than commenting
it out, and put the narrative of a change in its commit message.
