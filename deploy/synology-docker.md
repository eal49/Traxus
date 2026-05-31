# Traxus Server — Synology NAS Deployment Guide

Target: Synology DSM 7.x with Container Manager, using Docker Compose over SSH.

---

## Compatible models

This guide requires **Container Manager** (formerly Docker), which Synology ships for:

- All **x86-64** models (DS923+, DS1522+, DS920+, etc.)
- Select **ARM64** models (DS423+, DS723+, DS224+)

Entry-level ARM models (DS120j, DS218j, DS220j, etc.) do **not** support
Container Manager. If your NAS is ARM-based, check the
[Synology Compatibility List](https://www.synology.com/en-global/dsm/packages/ContainerManager)
before proceeding.

---

## Prerequisites

| Item | Where to configure |
|---|---|
| Container Manager installed | DSM → Package Center → search "Container Manager" |
| SSH service enabled | DSM → Control Panel → Terminal & SNMP → Enable SSH |
| Git installed (optional) | Package Center → search "Git Server" — only the client is needed |
| A domain or DDNS hostname | DSM → Control Panel → External Access → DDNS |

---

## 1. Create a shared folder for persistent data

All Traxus data (database, credentials) lives in a single folder on the NAS.

1. Open **DSM → Control Panel → Shared Folder** and click **Create**.
2. Name it `traxus`, leave other settings as defaults, and finish the wizard.

The folder is now at `/volume1/traxus` (adjust if your volume is named differently).

---

## 2. Get the code onto the NAS

SSH into the NAS:

```bash
ssh admin@<NAS_IP>
```

Clone the repository somewhere convenient (your home directory is fine — the
important persistent data goes in the shared folder, not here):

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/traxus.git traxus
cd traxus
```

If Git is not available, download and extract a release `.tar.gz` instead, then
`cd` into the extracted directory.

---

## 3. Configure the data directory

Tell Docker Compose where to store data:

```bash
export TRAXUS_DATA_DIR=/volume1/traxus
```

To make this permanent across reboots, add the line to `~/.bashrc` (or
`~/.profile` for login shells):

```bash
echo 'export TRAXUS_DATA_DIR=/volume1/traxus' >> ~/.bashrc
```

---

## 4. Build and start the server

From the `traxus` directory:

```bash
docker compose up -d --build
```

Verify the container started:

```bash
docker compose ps
# NAME      STATUS
# traxus    Up N seconds

docker compose logs
# Should end with:
# Traxus server listening on ws://0.0.0.0:8765
```

The server is now running on port **8765** on the NAS. Clients on the same
local network can connect directly with `ws://<NAS_IP>:8765`.

---

## 5. Reverse proxy for remote access (WSS + TLS)

To connect from outside your home network you need TLS (`wss://`). DSM's
built-in reverse proxy handles this — no Caddy or nginx needed.

### 5a. DDNS hostname

If you do not already have a domain pointing to your NAS public IP, set up DDNS:

1. **DSM → Control Panel → External Access → DDNS** → Add.
2. Choose a provider (Synology's own `*.synology.me` works).
3. Note the resulting hostname, e.g. `mynas.synology.me`.

> Your ISP must allow inbound port 443. If port 443 is blocked, choose an
> alternative port (e.g. 8443) and configure it in both the reverse proxy and
> your router's port-forwarding rule.

### 5b. Let's Encrypt certificate

1. **DSM → Control Panel → Security → Certificate** → Add.
2. Choose **Get a certificate from Let's Encrypt**.
3. Enter your DDNS hostname as the domain name and complete the wizard.

### 5c. Reverse proxy rule

1. **DSM → Control Panel → Login Portal → Advanced → Reverse Proxy** → Create.
2. Fill in:

| Field | Value |
|---|---|
| Reverse proxy name | `Traxus` |
| Source protocol | `HTTPS` |
| Source hostname | your DDNS hostname (e.g. `mynas.synology.me`) |
| Source port | `443` |
| Destination protocol | `HTTP` |
| Destination hostname | `localhost` |
| Destination port | `8765` |

3. On the **Custom Header** tab, click **Create → WebSocket**. This adds the
   `Upgrade` and `Connection` headers required for WebSocket proxying.

4. Click **Save**.

DSM will now proxy `wss://mynas.synology.me` → `ws://localhost:8765`.

---

## 6. Verify the connection

Install `websocat` on any machine that has internet access:

```bash
# Linux/macOS
curl -L https://github.com/vi/websocat/releases/latest/download/websocat.x86_64-unknown-linux-musl -o websocat
chmod +x websocat
./websocat wss://mynas.synology.me
```

Type the following and press Enter:

```json
{"type":"auth","username":"test"}
```

You should receive `{"type":"auth_ok",...}`. Press Ctrl+C to exit.

---

## 7. Enabling password authentication

By default the server runs in no-auth mode — any username connects without a
password. To require passwords:

### Create the credentials file

```bash
touch /volume1/traxus/users.json
chmod 600 /volume1/traxus/users.json
```

### Add user accounts

```bash
docker compose exec traxus python -m server.adduser alice
# Enter and confirm a password when prompted.
# Repeat for each user.
```

### Enable auth in the compose file

Edit `docker-compose.yml` and uncomment the `TRAXUS_USERS` line:

```yaml
environment:
  - TRAXUS_USERS=/data/users.json
```

Restart the container:

```bash
docker compose up -d
docker compose logs
# Expect: "Auth enabled: N user(s) loaded from /data/users.json"
```

---

## 8. Connecting clients

Users launch the Traxus client and enter:

```
wss://mynas.synology.me
```

in the server URL field on the login screen. On a local network, `ws://<NAS_IP>:8765` works without TLS.

---

## 9. Updating the server

```bash
cd ~/traxus
git pull
docker compose up -d --build
```

---

## Autostart after NAS reboot

The `restart: unless-stopped` policy in `docker-compose.yml` tells Docker to
restart the container automatically when the NAS reboots, as long as Container
Manager itself starts (which it does by default).

No additional configuration is needed.

---

## Troubleshooting

### Cannot connect via QuickConnect

**Symptom:** Clients cannot reach the server using a QuickConnect URL
(`https://quickconnect.to/...`).

**Cause:** QuickConnect is an HTTP relay designed for DSM web UI and Synology
apps. It does not proxy WebSocket connections. Use your DDNS hostname instead.

---

### WebSocket upgrade fails (HTTP 400 or 426 through reverse proxy)

**Symptom:** Client shows a connection error; DSM reverse proxy log shows
`400 Bad Request` or `426 Upgrade Required`.

**Cause:** The WebSocket upgrade headers are missing from the reverse proxy rule.

**Fix:** In **Control Panel → Login Portal → Advanced → Reverse Proxy**, edit
the Traxus rule, go to **Custom Header**, and click **Create → WebSocket** to
add the `Upgrade` and `Connection` headers.

---

### Container exits immediately after start

**Symptom:** `docker compose ps` shows `Exited (1)`.

**Diagnosis:**

```bash
docker compose logs
```

Common causes:

- **Port already in use** — another service is bound to 8765. Change the host
  port in `docker-compose.yml` (e.g. `"9000:8765"`) and update the reverse
  proxy destination port.
- **Data directory not writable** — ensure `/volume1/traxus` exists and the
  `admin` user can write to it.

---

### ISP blocks port 443

**Symptom:** Let's Encrypt certificate request fails; clients cannot reach the
server from outside the LAN.

**Fix:** Use a non-standard port (e.g. 8443):
1. Add a port-forwarding rule on your router: `8443 → NAS:8443`.
2. Change the reverse proxy source port from 443 to 8443.
3. Clients connect to `wss://mynas.synology.me:8443`.

---

## WebRTC audio — NAT traversal notes

Voice is peer-to-peer; audio never passes through the NAS. The NAS only relays
JSON signaling messages. See the
[VPS deployment guide](deploy.md#8-webrtc-audio--nat-traversal-notes)
for STUN/TURN details — the same notes apply here.
