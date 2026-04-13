## ADDED Requirements

### Requirement: Server-only requirements file exists
The repository SHALL contain `deploy/requirements-server.txt` listing only the dependencies required to run the server (excluding TUI and audio packages).

#### Scenario: File contains only websockets
- **WHEN** a developer reads `deploy/requirements-server.txt`
- **THEN** it SHALL list `websockets` with a version pin and no other runtime packages

### Requirement: Caddyfile configures reverse proxy with TLS
The repository SHALL contain `deploy/Caddyfile` that configures Caddy to terminate TLS for a Duck DNS subdomain and proxy WebSocket traffic to the local server port.

#### Scenario: Caddyfile targets Duck DNS hostname
- **WHEN** an operator replaces the placeholder hostname in `deploy/Caddyfile`
- **THEN** Caddy SHALL obtain a Let's Encrypt certificate for that hostname via HTTP-01 challenge and proxy all traffic to `localhost:8765`

#### Scenario: WebSocket connections are proxied
- **WHEN** a client connects to `wss://<hostname>`
- **THEN** Caddy SHALL forward the WebSocket upgrade and all subsequent frames to `ws://localhost:8765`

### Requirement: systemd service unit file exists
The repository SHALL contain `deploy/traxus-server.service` that runs the Traxus server as a systemd service.

#### Scenario: Service starts on boot
- **WHEN** the VPS boots
- **THEN** the `traxus-server` service SHALL start automatically via `WantedBy=multi-user.target`

#### Scenario: Service restarts on crash
- **WHEN** the server process exits with a non-zero code
- **THEN** systemd SHALL restart it after a short delay via `Restart=on-failure`

#### Scenario: Service binds to loopback only
- **WHEN** the service starts
- **THEN** `TRAXUS_HOST` SHALL be set to `127.0.0.1` so the server is not directly reachable from outside the VPS

### Requirement: Operator deployment guide exists
The repository SHALL contain `deploy/deploy.md` with step-by-step instructions for deploying the Traxus server on an Ubuntu 24.04 VPS with Duck DNS and Caddy.

#### Scenario: Guide covers VM provisioning
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for provisioning an Ubuntu 24.04 VPS and configuring the provider firewall to allow ports 22, 80, and 443

#### Scenario: Guide covers Duck DNS setup
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for registering a Duck DNS subdomain and pointing it to the VPS public IP

#### Scenario: Guide covers Python and dependency installation
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for installing Python 3.12, cloning the repository, and installing `deploy/requirements-server.txt`

#### Scenario: Guide covers Caddy installation and configuration
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for installing Caddy, placing the Caddyfile, and starting the Caddy service

#### Scenario: Guide covers systemd service activation
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for installing `traxus-server.service`, enabling it, and starting it

#### Scenario: Guide covers firewall configuration
- **WHEN** an operator reads `deploy/deploy.md`
- **THEN** they SHALL find instructions for configuring `ufw` to allow ports 22, 80, and 443 and deny direct access to port 8765

#### Scenario: Guide includes verification step
- **WHEN** an operator completes all setup steps
- **THEN** `deploy/deploy.md` SHALL provide a command to verify the server is reachable at `wss://<hostname>`

### Requirement: Login screen default URL is blank
The client login screen SHALL default to an empty server URL field rather than `ws://localhost:8765`.

#### Scenario: Fresh client shows empty URL field
- **WHEN** a user launches the client for the first time
- **THEN** the server URL input field SHALL be empty, prompting the user to enter their server address

#### Scenario: Localhost still works when typed manually
- **WHEN** a user types `ws://localhost:8765` into the URL field and connects
- **THEN** the client SHALL connect to a local server as before
