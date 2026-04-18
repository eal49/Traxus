## Requirements

### Requirement: User can set a custom local nick color
The client SHALL allow the user to choose a color for their own nickname. The color SHALL be stored in `settings.json` under the key `nick_color` as a lowercase hex string (e.g. `"#5865f2"`). An empty string means default (white).

#### Scenario: Nick color persists across restarts
- **WHEN** the user sets a nick color and restarts the client
- **THEN** their nickname SHALL render in the previously chosen color

#### Scenario: Default color is white
- **WHEN** no `nick_color` key exists in settings
- **THEN** the user's nickname SHALL render as bold white (current behavior)

#### Scenario: Reset reverts to default
- **WHEN** the user runs `/color reset`
- **THEN** `nick_color` SHALL be set to `""` and their nick SHALL render white again

### Requirement: /color command sets nick color immediately
The `/color` command SHALL accept a predefined name or a hex value. It SHALL update the color in memory and persist it to `settings.json` without requiring a client restart.

#### Scenario: Setting by predefined name
- **WHEN** the user runs `/color blue`
- **THEN** `nick_color` SHALL be set to `#5865f2` and confirmed with a local message

#### Scenario: Setting by hex value
- **WHEN** the user runs `/color #ff5500`
- **THEN** `nick_color` SHALL be set to `#ff5500` and confirmed with a local message

#### Scenario: Invalid hex rejected
- **WHEN** the user runs `/color #gg0000`
- **THEN** a local error message SHALL be shown and `nick_color` SHALL remain unchanged

#### Scenario: Unknown name rejected
- **WHEN** the user runs `/color purple`
- **THEN** a local error message listing valid names SHALL be shown

### Requirement: Predefined color names map to fixed hex values
The following names SHALL be accepted by `/color` and map to the palette colors already used for other users:

| Name    | Hex       |
|---------|-----------|
| blue    | #5865f2   |
| green   | #57f287   |
| yellow  | #fee75c   |
| pink    | #eb459e   |
| red     | #ed4245   |
| cyan    | #00b0f4   |
| magenta | #f47fff   |
| orange  | #faa61a   |
| white   | #ffffff   |

#### Scenario: All predefined names accepted
- **WHEN** the user runs `/color <name>` for any name in the table above
- **THEN** the nick color SHALL be set to the corresponding hex value

### Requirement: Self-nick renders in chosen color
`MessageView.add_chat()` SHALL render the calling user's nickname in the color stored in `settings.json` rather than the hardcoded white.

#### Scenario: Chosen color applied to self-nick
- **WHEN** a chat message arrives from the local user and `nick_color` is `"#ff5500"`
- **THEN** the nickname SHALL be rendered as `[bold #ff5500]nick[/bold #ff5500]`

#### Scenario: Default white used when no color set
- **WHEN** a chat message arrives from the local user and `nick_color` is `""`
- **THEN** the nickname SHALL be rendered as `[bold white]nick[/bold white]`
