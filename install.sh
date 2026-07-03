#!/usr/bin/env bash
# Install the ip-beacon service. Run with root (sudo ./install.sh).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
