## ADDED Requirements

### Requirement: Server broadcasts user_online on connect
When any client successfully authenticates, the server SHALL broadcast a `user_online` message to every other connected client. The message SHALL include the newly authenticated client's username.

#### Scenario: user_online sent to all peers on auth
- **WHEN** a client authenticates successfully
- **THEN** all other connected clients SHALL receive `{"type": "user_online", "username": "<new user>"}`

#### Scenario: user_online not sent to the authenticating client itself
- **WHEN** a client authenticates successfully
- **THEN** the authenticating client SHALL NOT receive its own `user_online` event

### Requirement: Server broadcasts user_offline on disconnect
When any client disconnects, the server SHALL broadcast a `user_offline` message to every remaining connected client. The message SHALL include the disconnected client's username.

#### Scenario: user_offline sent on clean disconnect
- **WHEN** a connected and authenticated client closes the WebSocket connection
- **THEN** all remaining connected clients SHALL receive `{"type": "user_offline", "username": "<departed user>"}`

#### Scenario: user_offline sent on abnormal disconnect
- **WHEN** a connected client's WebSocket connection drops without a clean close
- **THEN** all remaining connected clients SHALL receive `{"type": "user_offline", "username": "<departed user>"}`

### Requirement: auth_ok response includes online and known user snapshots
The `auth_ok` response sent to a newly authenticated client SHALL include an `online_users` field listing all currently connected usernames. When the server is running with `TRAXUS_USERS` configured, `auth_ok` SHALL also include a `known_users` field listing all registered usernames (including those currently offline). When `TRAXUS_USERS` is not configured, `known_users` SHALL equal `online_users`.

#### Scenario: online_users present in auth_ok
- **WHEN** a client receives `auth_ok`
- **THEN** the payload SHALL include `"online_users": [<list of currently connected usernames>]`

#### Scenario: online_users includes all peers connected at auth time
- **WHEN** three clients are connected and a fourth authenticates
- **THEN** the fourth client's `auth_ok` SHALL list all three existing usernames in `online_users`

#### Scenario: known_users includes offline registered users when auth is enabled
- **WHEN** the server is configured with `TRAXUS_USERS` and a registered user is not currently connected
- **THEN** that username SHALL appear in `known_users` but not in `online_users` in the `auth_ok` sent to newly connecting clients

#### Scenario: known_users equals online_users when auth is disabled
- **WHEN** the server is running without `TRAXUS_USERS` configured
- **THEN** `known_users` in `auth_ok` SHALL equal `online_users`

### Requirement: Client maintains a server-wide user roster
The client SHALL maintain two sets from the moment `auth_ok` is received: `online_users` (currently connected) and `known_offline_users` (known but not connected). These sets SHALL be updated in response to `user_online` and `user_offline` events for the duration of the session.

#### Scenario: Roster populated from auth_ok
- **WHEN** the client receives `auth_ok` with `online_users` and `known_users`
- **THEN** `online_users` SHALL be stored as the online set and `known_users \ online_users` SHALL be stored as the offline set

#### Scenario: user_online event adds to online set
- **WHEN** the client receives a `user_online` event
- **THEN** that username SHALL be added to the online set and removed from the offline set if present

#### Scenario: user_offline event moves user to offline set
- **WHEN** the client receives a `user_offline` event for a username in the online set
- **THEN** that username SHALL be removed from the online set and, if it was in `known_users`, added to the offline set
