#!/usr/bin/env bash
# Install the ip-beacon service, locally or on a remote Linux host.
#
#   sudo ./install.sh              install on this machine
#   ./install.sh [user@]<host>     copy this repo to <host> over ssh and
#                                   install + activate there (sudo on the
#                                   remote host, via ssh -t)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -gt 0 ]]; then
    target="$1"
    remote_dir="$(ssh "${target}" mktemp -d)"
    echo "[ip-beacon] copying repo -> ${target}:${remote_dir}"
    scp -q "${here}/ip-beacon.py" "${here}/ip-beacon.service" "${here}/install.sh" "${target}:${remote_dir}/"
    echo "[ip-beacon] running installer on ${target}"
    ssh -t "${target}" "sudo bash '${remote_dir}/install.sh' && rm -rf '${remote_dir}'"
    exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
    echo "This installer needs root. Re-run: sudo $0" >&2
    exit 1
fi

echo "[ip-beacon] installing script -> /usr/local/bin/ip-beacon.py"
install -m 0755 "${here}/ip-beacon.py" /usr/local/bin/ip-beacon.py

echo "[ip-beacon] installing unit   -> /etc/systemd/system/ip-beacon.service"
install -m 0644 "${here}/ip-beacon.service" /etc/systemd/system/ip-beacon.service

echo "[ip-beacon] reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable --now ip-beacon.service

# If ufw is active, open the port (no-op if ufw is inactive/absent).
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    echo "[ip-beacon] ufw is active; allowing 55555/udp"
    ufw allow 55555/udp || true
fi

echo
echo "[ip-beacon] status:"
systemctl --no-pager --full status ip-beacon.service || true
