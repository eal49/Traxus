## MODIFIED Requirements

### Requirement: PTT key is bound via key capture
The PTT key capture screen SHALL wait for the user to press any key or click any mouse button and use that input as the new PTT binding. The binding SHALL take effect immediately.

#### Scenario: Capture screen prompts the user
- **WHEN** the PTT key capture screen is displayed
- **THEN** it SHALL show the current PTT binding and a prompt instructing the user to press any key or click a mouse button, or press Escape to cancel

#### Scenario: Pressing a key sets PTT immediately
- **WHEN** the user presses any key (other than Escape) on the capture screen
- **THEN** that key SHALL become the new PTT binding from that point forward, without restarting the client

#### Scenario: Clicking a mouse button sets PTT immediately
- **WHEN** the user clicks any mouse button on the capture screen
- **THEN** that mouse button SHALL become the new PTT binding from that point forward, stored as `"mouseN"`, without restarting the client

#### Scenario: Escape cancels without changing binding
- **WHEN** the user presses Escape on the capture screen
- **THEN** the PTT binding SHALL remain unchanged and the screen SHALL close

#### Scenario: Default PTT key is F9
- **WHEN** no settings file exists
- **THEN** the PTT key SHALL default to F9

### Requirement: Selecting PTT Key opens key capture screen
The settings menu entry labelled "PTT Key" SHALL open a capture screen that accepts both keyboard and mouse input.

#### Scenario: Selecting PTT Key opens key capture screen
- **WHEN** the user selects "PTT Key" from the settings menu
- **THEN** a key capture screen SHALL appear prompting the user to press any key or click a mouse button
