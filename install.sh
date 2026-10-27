#!/usr/bin/env bash
# Install the ip-beacon service, locally or on a remote Linux host.
#
#   sudo ./install.sh [DNS]              install on this machine
#   ./install.sh [DNS] [user@]<host>     copy this repo to <host> over ssh and
#                                         install + activate there (sudo on the
#                                         remote host, via ssh -t)
#
# DNS is --dns HOST=NAME[,HOST=NAME...] --upstream IP[,IP...]. It also installs
# dnsmasq and ip-beacon-dns.service, which answer each NAME with the address
# HOST's beacons come from while they keep arriving, and forward every other
# query to the upstream servers. dnsmasq listens on the default route's
# interface and the loopback. Debian-based hosts only; needs apt for dnsmasq.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

dns_map="" upstream="" target=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dns) dns_map="$2"; shift 2 ;;
        --upstream) upstream="$2"; shift 2 ;;
        -*) echo "unknown option $1" >&2; exit 2 ;;
        *) target="$1"; shift ;;
    esac
done
if [[ -n "${dns_map}" && -z "${upstream}" ]]; then
    echo "--dns needs --upstream; the host's own resolver may forward back to it" >&2
    exit 2
fi
remote_args=""
if [[ -n "${dns_map}" ]]; then
    remote_args="$(printf '%q ' --dns "${dns_map}" --upstream "${upstream}")"
fi

if [[ -n "${target}" ]]; then
    remote_dir="$(ssh "${target}" mktemp -d)"
    echo "[ip-beacon] copying repo -> ${target}:${remote_dir}"
    scp -q "${here}/ip-beacon.py" "${here}/ip-beacon.service" "${here}/listener.py" \
        "${here}/ip-beacon-dns.service" "${here}/install.sh" "${target}:${remote_dir}/"
    echo "[ip-beacon] running installer on ${target}"
    ssh -t "${target}" "sudo bash '${remote_dir}/install.sh' ${remote_args}&& rm -rf '${remote_dir}'"
    exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
    echo "This installer needs root. Re-run: sudo $0" >&2
    exit 1
fi

ufw_allow() {
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
        echo "[ip-beacon] ufw is active; allowing $1"
        ufw allow "$1" || true
    fi
}

echo "[ip-beacon] installing script -> /usr/local/bin/ip-beacon.py"
install -m 0755 "${here}/ip-beacon.py" /usr/local/bin/ip-beacon.py

echo "[ip-beacon] installing unit   -> /etc/systemd/system/ip-beacon.service"
install -m 0644 "${here}/ip-beacon.service" /etc/systemd/system/ip-beacon.service

echo "[ip-beacon] reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable --now ip-beacon.service
ufw_allow 55555/udp

if [[ -n "${dns_map}" ]]; then
    echo "[ip-beacon] installing DNS listener -> /usr/local/bin/ip-beacon-listener.py"
    id -u ip-beacon >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin ip-beacon
    install -m 0755 "${here}/listener.py" /usr/local/bin/ip-beacon-listener.py
    install -m 0644 "${here}/ip-beacon-dns.service" /etc/systemd/system/ip-beacon-dns.service
    printf 'BEACON_DNS_MAP=%s\n' "${dns_map}" > /etc/default/ip-beacon-dns
    systemctl daemon-reload
    systemctl enable ip-beacon-dns.service
    systemctl restart ip-beacon-dns.service

    # Written before dnsmasq is installed, so its first start already ignores
    # the host's resolver, which may forward back here.
    interface="$(ip route show default | awk '{print $5; exit}')"
    echo "[ip-beacon] configuring dnsmasq on ${interface} -> /etc/dnsmasq.d/ip-beacon-dns.conf"
    mkdir -p /etc/dnsmasq.d
    {
        echo "# Written by ip-beacon's install.sh --dns."
        echo "interface=${interface}"
        echo "interface=lo"
        echo "bind-dynamic"
        echo "no-resolv"
        tr ',' '\n' <<<"${upstream}" | sed 's/^/server=/'
        echo "domain-needed"
        echo "bogus-priv"
        echo "hostsdir=/var/lib/ip-beacon-dns"
        echo "local-ttl=10"
    } > /etc/dnsmasq.d/ip-beacon-dns.conf
    if ! dpkg-query -W -f='${Status}' dnsmasq 2>/dev/null | grep -q "ok installed"; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y dnsmasq
    fi
    systemctl enable dnsmasq.service
    systemctl restart dnsmasq.service
    ufw_allow 53
fi

echo
echo "[ip-beacon] status:"
systemctl --no-pager --full status ip-beacon.service || true
if [[ -n "${dns_map}" ]]; then
    systemctl --no-pager --full status ip-beacon-dns.service dnsmasq.service || true
fi
