## Purpose

Define the self-service password change capability: the `/passwd` command, the `ChangePasswordScreen` modal, the wire protocol, and server-side validation rules.

## Requirements

### Requirement: /passwd command opens a change-password modal
The client SHALL provide a `/passwd` slash command that opens a `ChangePasswordScreen` modal when the server is running in auth mode.

#### Scenario: /passwd opens modal in auth mode
- **WHEN** the user types `/passwd` and the server indicated auth mode (password was required at login)
- **THEN** the client SHALL push a `ChangePasswordScreen` modal over the chat screen

#### Scenario: /passwd rejected when auth is disabled
- **WHEN** the user types `/passwd` and the server is running in no-auth mode
- **THEN** the client SHALL display a local error message "Password authentication is not enabled on this server" and SHALL NOT open the modal

### Requirement: ChangePasswordScreen collects current and new password
The `ChangePasswordScreen` SHALL present three masked input fields: current password, new password, and confirm new password.

#### Scenario: Three masked fields present
- **WHEN** `ChangePasswordScreen` is displayed
- **THEN** it SHALL show exactly three password inputs: "Current password", "New password", and "Confirm new password", all masked

#### Scenario: Save button sends change_password message
- **WHEN** the user fills all three fields and presses Save
- **THEN** the client SHALL send `{ type: "change_password", old_password: <current>, new_password: <new> }` to the server

#### Scenario: Confirm mismatch shows client-side error
- **WHEN** the new password and confirm fields do not match
- **THEN** the client SHALL display "Passwords do not match" inside the modal and SHALL NOT send the message

#### Scenario: Escape cancels without sending
- **WHEN** the user presses Escape or activates Cancel
- **THEN** the modal SHALL close without sending any message

### Requirement: Server validates and applies password change
On receiving `change_password`, the server SHALL verify the old password, enforce policy on the new password, update the credentials file, and respond.

#### Scenario: Successful change
- **WHEN** the server receives `change_password` with a correct old password and a valid new password
- **THEN** the server SHALL hash the new password, write it to the credentials file, clear the `must_change` flag for that user, and send `{ type: "password_changed" }`

#### Scenario: Wrong current password
- **WHEN** the server receives `change_password` with an incorrect old password
- **THEN** the server SHALL send `{ type: "password_change_error", reason: "wrong_password" }` and SHALL NOT modify the credentials file

#### Scenario: New password too short
- **WHEN** the server receives `change_password` with a new password shorter than 10 characters
- **THEN** the server SHALL send `{ type: "password_change_error", reason: "too_short" }` and SHALL NOT modify the credentials file

#### Scenario: New password same as old
- **WHEN** the server receives `change_password` with a new password identical to the current password
- **THEN** the server SHALL send `{ type: "password_change_error", reason: "same_password" }` and SHALL NOT modify the credentials file

#### Scenario: change_password rejected in no-auth mode
- **WHEN** the server receives `change_password` and no credentials file is loaded
- **THEN** the server SHALL send `{ type: "password_change_error", reason: "auth_disabled" }`

### Requirement: Client handles change_password server responses
The client SHALL close the modal on success and display an inline error on failure.

#### Scenario: password_changed closes modal
- **WHEN** the client receives `{ type: "password_changed" }`
- **THEN** the `ChangePasswordScreen` SHALL close and the must_change nudge in the status bar SHALL be cleared

#### Scenario: password_change_error shown in modal
- **WHEN** the client receives `{ type: "password_change_error", reason: <reason> }`
- **THEN** the modal SHALL remain open and display a human-readable error message corresponding to the reason
