# Traxus Server — VPS Deployment Guide

Target: Oracle Cloud Always Free (ARM Ampere A1, Ubuntu 24.04) + Duck DNS + Caddy + systemd.

---

## 1. Oracle Cloud VM Provisioning

1. Sign in to [cloud.oracle.com](https://cloud.oracle.com) and navigate to **Compute → Instances → Create Instance**.
2. Choose a name (e.g. `traxus-server`).
3. Under **Image and shape**, click **Change image** → select **Ubuntu 24.04**.
4. Under **Shape**, click **Change shape** → select **Ampere** → choose `VM.Standard.A1.Flex` with **1 OCPU** and **6 GB RAM** (Always Free eligible).
5. Under **Add SSH keys**, upload your public key (`~/.ssh/id_rsa.pub`) or paste it in.
6. Click **Create**.

**Open ports in the Security List:**

Once the instance is running, go to its **VCN → Security List** and add three ingress rules:

| Source CIDR | Protocol | Port | Description |
|---|---|---|---|
| 0.0.0.0/0 | TCP | 22 | SSH |
| 0.0.0.0/0 | TCP | 80 | HTTP (ACME challenge) |
| 0.0.0.0/0 | TCP | 443 | HTTPS / WSS |

Do **not** open port 8765 — the server binds to loopback only.

Note the **Public IP address** of your instance for the next step.

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
git clone https://github.com/YOUR_USERNAME/traxus.git
cd traxus
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

Copy and edit the Caddyfile:

```bash
sudo cp ~/traxus/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
# Replace YOUR-NAME.duckdns.org with your actual subdomain
```

Enable and start Caddy:

```bash
sudo systemctl enable --now caddy
sudo systemctl status caddy   # should show "active (running)"
```

Caddy will automatically obtain a Let's Encrypt certificate on first startup. Port 80 must be open for the HTTP-01 challenge to succeed.

---

## 5. systemd Service

Copy the service file and reload systemd:

```bash
sudo cp ~/traxus/deploy/traxus-server.service /etc/systemd/system/
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

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8765/tcp
sudo ufw enable
sudo ufw status
```

---

## 7. Verification

Check that the server is reachable over WSS. Install `websocat`:

```bash
curl -L https://github.com/vi/websocat/releases/latest/download/websocat.aarch64-unknown-linux-musl -o websocat
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

## Connecting Clients

Users launch the Traxus client and enter:

```
wss://YOUR-NAME.duckdns.org
```

in the server URL field on the login screen.

---

## Updating the Server

```bash
cd ~/traxus
git pull
sudo systemctl restart traxus-server
```

Note: a restart clears all in-memory state (channels reset to defaults, history lost).
