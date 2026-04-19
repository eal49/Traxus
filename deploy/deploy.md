# Traxus Server — VPS Deployment Guide

Target: Any Ubuntu 24.04 VPS (x86-64) + Duck DNS + Caddy + systemd.

---

## 1. VPS Provisioning

Provision a VPS running **Ubuntu 24.04 LTS** (x86-64) with at least 1 vCore and 1 GB RAM. Any provider works (OVH, Hetzner, Linode, etc.).

**Open the required ports** in your provider's firewall / security group panel:

| Protocol | Port | Purpose |
|---|---|---|
| TCP | 22 | SSH |
| TCP | 80 | HTTP (ACME challenge for Let's Encrypt) |
| TCP | 443 | HTTPS / WSS |

Do **not** open port 8765 — the server binds to loopback only.

Note the **public IP address** of your instance for the next step.

---

## 2. Duck DNS Setup

1. Go to [duckdns.org](https://www.duckdns.org) and sign in with Google, GitHub, or Reddit.
2. Enter a subdomain name (e.g. `traxus`) and click **Add domain**.
3. In the **current ip** field, enter your VPS public IP and click **Update IP**.

Your server will be reachable at `wss://traxus.duckdns.org` (substitute your chosen name).

---

## 3. Python, Repo, and Dependencies

SSH into your VPS:

```bash
ssh ubuntu@<YOUR_VPS_IP>
```

Install Python 3.12 and pip (Ubuntu 24.04 ships Python 3.12):

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/YOUR_USERNAME/traxus.git Traxus
cd Traxus
python3 -m venv .venv
.venv/bin/pip install -r deploy/requirements-server.txt
```

Verify the server starts:

```bash
TRAXUS_HOST=127.0.0.1 .venv/bin/python -m server.main
# Should print: Traxus server listening on ws://127.0.0.1:8765
# Press Ctrl+C to stop
```

---

## 4. Caddy (TLS Reverse Proxy)

Install Caddy:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Write the Caddyfile, substituting your actual subdomain:

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null << 'EOF'
YOUR-NAME.duckdns.org {
    reverse_proxy localhost:8765
}
EOF
```

The complete file should look like this (example for `traxus.duckdns.org`):

```
traxus.duckdns.org {
    reverse_proxy localhost:8765
}
```

Caddy's `reverse_proxy` directive transparently upgrades WebSocket connections,
so no extra `header` or `websocket` stanza is needed. The bare site block is
sufficient — Caddy handles ACME, TLS termination, and WS upgrade automatically.

Enable and start Caddy:

```bash
sudo systemctl enable --now caddy
sudo systemctl status caddy   # should show "active (running)"
```

Caddy will automatically obtain a Let's Encrypt certificate on first startup. Ports 80 and 443 must be reachable from the internet — complete Section 6 (Firewall) first if you have not already done so.

---

## 5. systemd Service

Copy the service file and reload systemd:

```bash
sudo cp ~/Traxus/deploy/traxus-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now traxus-server
sudo systemctl status traxus-server   # should show "active (running)"
```

View logs at any time:

```bash
sudo journalctl -u traxus-server -f
```

---

## 6. Firewall

### Option A — UFW (simpler, recommended if you have no existing rules)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8765/tcp
sudo ufw enable
sudo ufw status
```

### Option B — iptables (if you manage rules directly)

If you already use iptables, skip UFW entirely — enabling it on top of existing iptables rules can cause conflicts.

The minimum required ruleset:

```bash
# Allow established/related return traffic (critical — without this, outbound
# replies are dropped and Caddy cannot reach Let's Encrypt)
sudo iptables -I INPUT 1 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow inbound SSH, HTTP (ACME challenge), and HTTPS
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Block direct access to the Traxus backend (loopback only)
sudo iptables -A INPUT -p tcp --dport 8765 -j DROP

# Drop everything else
sudo iptables -A INPUT -j DROP
```

Persist rules across reboots:

```bash
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

> **Note:** Ubuntu 24.04 defaults to the nftables backend. If `iptables --version`
> shows `(nf_tables)`, the `iptables` command is a compatibility shim. Rules
> saved via `iptables-persistent` may not survive reboots in this case — use
> `nft` directly instead, or install `iptables-legacy` and pin the alternative:
> ```bash
> sudo update-alternatives --set iptables /usr/sbin/iptables-legacy
> sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
> ```

---

## 7. Verification

Check that the server is reachable over WSS. Install `websocat`:

```bash
curl -L https://github.com/vi/websocat/releases/latest/download/websocat.x86_64-unknown-linux-musl -o websocat
chmod +x websocat
./websocat wss://YOUR-NAME.duckdns.org
# Type {"type":"auth","username":"test"} and press Enter
# You should receive {"type":"auth_ok",...}
# Press Ctrl+C to exit
```

If `websocat` is not available, a quick curl test confirms port 443 is open:

```bash
curl -I https://YOUR-NAME.duckdns.org
# Expect: HTTP/2 426 (Upgrade Required — the server expects a WebSocket upgrade, not HTTP)
```

---

## 8. WebRTC Audio — NAT Traversal Notes

Voice audio in Traxus is **peer-to-peer via WebRTC**. The server only relays JSON signaling messages (`voice_offer`, `voice_answer`, `voice_ice`); audio never passes through the VPS. This means:

- No audio-related bandwidth or CPU load on the server.
- No extra ports need to be opened on the server firewall.

Clients use the default STUN server (`stun:stun.l.google.com:19302`) to discover their public IP and negotiate a direct connection. This works for most NAT configurations (full-cone, port-restricted, address-restricted).

### When STUN is not enough

If two clients are both behind **strict symmetric NAT** (common on some corporate or mobile networks), STUN cannot establish a direct path and the WebRTC connection will fail silently — the users will hear nothing.

The fix is a **TURN server**, which relays audio when direct P2P is impossible. A minimal self-hosted option is [coturn](https://github.com/coturn/coturn):

```bash
sudo apt install -y coturn
```

Edit `/etc/turnserver.conf`:

```
listening-port=3478
tls-listening-port=5349
fingerprint
lt-cred-mech
user=traxus:YOUR_TURN_PASSWORD
realm=YOUR-NAME.duckdns.org
cert=/path/to/fullchain.pem
pkey=/path/to/privkey.pem
```

Open the additional ports in your firewall:

```bash
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp
sudo ufw allow 5349/udp
sudo ufw allow 49152:65535/udp   # TURN relay range
```

Enable and start:

```bash
sudo systemctl enable --now coturn
```

Each client then sets `stun_server` in `~/.traxus/settings.json` to the TURN URL:

```json
{
  "stun_server": "turn:traxus:YOUR_TURN_PASSWORD@YOUR-NAME.duckdns.org:3478"
}
```

> **Note:** TURN relay adds latency and server bandwidth proportional to the number of active voice pairs that cannot connect directly. For small private servers this is usually negligible.

---

## Connecting Clients

Users launch the Traxus client and enter:

```
wss://YOUR-NAME.duckdns.org
```

in the server URL field on the login screen.

---

## Updating the Server

```bash
cd ~/Traxus
git pull
sudo systemctl restart traxus-server
```

Note: a restart clears all in-memory state (channels reset to defaults, history lost).

---

## Troubleshooting

### Caddy cannot obtain a TLS certificate

**Symptom:** `journalctl -u caddy` shows repeated `HTTP request failed; retrying` against
`acme-v02.api.letsencrypt.org`, then `could not get certificate from issuer`.

**Cause:** Caddy must make outbound HTTPS requests to Let's Encrypt to complete the ACME
challenge. If your INPUT chain has a blanket DROP rule at the bottom but no rule accepting
established/related return traffic, reply packets from Let's Encrypt are dropped.

**Fix:** Insert the conntrack rule at the top of INPUT (before any DROP):

```bash
sudo iptables -I INPUT 1 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo netfilter-persistent save
```

Verify outbound is now working:

```bash
curl -I https://acme-v02.api.letsencrypt.org/directory
# Expect: HTTP/2 200
```

---

### Caddy starts but does not attempt certificate renewal

**Symptom:** After fixing the iptables rule and restarting Caddy, the `tls.obtain` log
messages no longer appear — Caddy never tries to obtain the certificate.

**Cause:** Caddy uses exponential backoff after repeated ACME failures. The backoff state
is stored on disk and survives restarts.

**Fix:** Clear the cached ACME state and restart:

```bash
sudo systemctl stop caddy
sudo rm -rf /var/lib/caddy/.local/share/caddy/certificates/
sudo systemctl start caddy
sudo journalctl -u caddy -f
# Expect: "certificate obtained successfully" within ~30 seconds
```

---

### EOF errors in Caddy logs from unknown IPs

**Symptom:** `journalctl -u caddy` shows repeated `"msg":"EOF"` errors from IP addresses
you do not recognise hitting port 80.

**Cause:** Normal internet scanner traffic. Public port 80 receives constant automated
probes. These are harmless and unrelated to the ACME challenge or Traxus functionality.

---

### iptables rules lost after reboot

**Symptom:** Firewall rules are correct after manual setup but disappear on reboot.

**Cause:** Either `iptables-persistent` is not installed, or Ubuntu 24.04's nftables
backend is active and the `iptables` shim rules are not persisted by `netfilter-persistent`.

**Fix:** Check which backend is active:

```bash
iptables --version
# "legacy" → use iptables-persistent as normal
# "nf_tables" → pin the legacy backend first:
sudo update-alternatives --set iptables /usr/sbin/iptables-legacy
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
```

Then save:

```bash
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```
