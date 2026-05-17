# password-renewal-nudge Specification

## Purpose
TBD - created by archiving change user-password-change. Update Purpose after archive.
## Requirements
### Requirement: Status bar shows nudge when must_change_password is set
When `auth_ok` carries `must_change_password: true`, the client SHALL append a visible nudge to the status bar until the password is changed.

#### Scenario: Nudge visible after login with must_change flag
- **WHEN** the client receives `auth_ok` with `must_change_password: true`
- **THEN** the status bar SHALL display a suffix such as `⚠ /passwd` appended to the normal connection line

#### Scenario: No nudge when flag is absent or false
- **WHEN** the client receives `auth_ok` without `must_change_password` or with `must_change_password: false`
- **THEN** the status bar SHALL show the normal connection line with no additional suffix

### Requirement: Nudge is cleared after successful password change
The nudge SHALL disappear as soon as the server confirms the change.

#### Scenario: Nudge removed on password_changed
- **WHEN** the client receives `{ type: "password_changed" }`
- **THEN** the status bar nudge SHALL be removed immediately

#### Scenario: Nudge persists if change fails or is cancelled
- **WHEN** the user opens ChangePasswordScreen and then cancels, or receives a password_change_error
- **THEN** the status bar nudge SHALL remain visible

### Requirement: Nudge does not block any functionality
The soft nudge is informational only. Text chat, voice channels, and all commands SHALL remain fully functional regardless of whether the nudge is displayed.

#### Scenario: Chat works while nudge is active
- **WHEN** the status bar nudge is displayed
- **THEN** the user SHALL be able to send messages, join channels, and use voice without restriction

