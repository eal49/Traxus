## ADDED Requirements

### Requirement: Mouse button can be selected as PTT binding
The client SHALL accept a mouse button press on the PTT key capture screen and use that button as the new PTT binding.

#### Scenario: Clicking a mouse button captures the binding
- **WHEN** the PTT key capture screen is displayed and the user clicks any mouse button
- **THEN** that mouse button SHALL become the new PTT binding, stored as `"mouseN"` where N is the button number (1=left, 2=right, 3=middle, 4/5=side)

#### Scenario: Mouse binding takes effect immediately
- **WHEN** the user selects a mouse button as the PTT binding
- **THEN** pressing that mouse button SHALL toggle PTT from that point forward without restarting the client

#### Scenario: Mouse binding is persisted
- **WHEN** the user selects a mouse button as the PTT binding
- **THEN** the binding SHALL be saved to `~/.config/traxus/settings.json` as `"mouseN"` and restored on next launch

### Requirement: PTT toggle fires on configured mouse button press
The client SHALL toggle PTT when the configured mouse button is pressed, using the same toggle mechanism as the keyboard PTT handler.

#### Scenario: Configured mouse button toggles PTT
- **WHEN** the user has configured a mouse button (e.g., `"mouse3"`) as the PTT key and presses that button
- **THEN** PTT SHALL toggle on or off, identical to the keyboard PTT behaviour

#### Scenario: Non-configured mouse buttons do not trigger PTT
- **WHEN** the user presses a mouse button that does not match the configured PTT binding
- **THEN** PTT SHALL NOT be toggled

#### Scenario: Left click conflict warning
- **WHEN** the PTT capture screen is visible
- **THEN** the prompt SHALL warn that mouse button 1 (left click) conflicts with normal UI interaction

### Requirement: Capture screen accepts both keyboard keys and mouse buttons
The PTT key capture screen SHALL capture whichever input arrives first — a keypress or a mouse button click.

#### Scenario: Capture prompt mentions mouse buttons
- **WHEN** the PTT key capture screen is displayed
- **THEN** the prompt SHALL instruct the user that they may press any key OR click a mouse button

#### Scenario: Escape still cancels without binding a mouse button
- **WHEN** the PTT key capture screen is displayed and the user presses Escape
- **THEN** the PTT binding SHALL remain unchanged regardless of any prior mouse movement
