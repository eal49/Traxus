## ADDED Requirements

### Requirement: /passwd command is documented
`docs/commands.md` SHALL include an entry for `/passwd` following the same format as existing command entries.

#### Scenario: /passwd entry present
- **WHEN** a developer opens `docs/commands.md`
- **THEN** they SHALL find an entry for `/passwd` describing: syntax (`/passwd`), no arguments, opens the ChangePasswordScreen modal, sends `change_password` to the server, and that it is disabled with an error message when the server has no auth mode enabled
