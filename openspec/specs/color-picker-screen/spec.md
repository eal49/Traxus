## Requirements

### Requirement: ColorPickerScreen displays a 32×16 HSV color grid
The `ColorPickerScreen` SHALL render a grid of 512 colored cells arranged as 32 columns (hues) × 16 rows (saturation/value variants). Each cell SHALL be displayed as two block characters (`██`) colored with the cell's RGB value as a Rich inline background color. Rows 14–15 SHALL display a 64-step grayscale ramp instead of hues.

#### Scenario: Grid contains 512 cells
- **WHEN** the `ColorPickerScreen` is rendered
- **THEN** the grid SHALL contain exactly 32 columns and 16 rows

#### Scenario: Grayscale ramp on bottom rows
- **WHEN** the grid is rendered
- **THEN** rows 14 and 15 SHALL display a continuous grayscale ramp from white to near-black across 64 cells

### Requirement: Cursor navigates the grid with arrow keys
The screen SHALL maintain a (row, col) cursor. Arrow keys SHALL move the cursor one step in the pressed direction, clamping at grid boundaries. The selected cell SHALL render as `◆◆` (with the cell's background color) instead of `██`. A `▼` indicator SHALL appear below the grid at the horizontal position of the selected column.

#### Scenario: Arrow keys move cursor
- **WHEN** the user presses ← or →
- **THEN** the selected column SHALL decrease or increase by 1 (clamped to 0–31)
- **WHEN** the user presses ↑ or ↓
- **THEN** the selected row SHALL decrease or increase by 1 (clamped to 0–15)

#### Scenario: Column indicator position matches selected column
- **WHEN** the cursor is at column N
- **THEN** the `▼` indicator SHALL appear at horizontal offset N×2 characters below the grid

#### Scenario: Selected cell uses cursor marker
- **WHEN** the cursor is at (row, col)
- **THEN** that cell SHALL render as `◆◆` on the cell's background color

### Requirement: Live preview shows nick in selected color
The screen SHALL display a preview line showing the user's nickname rendered in the currently selected color, followed by sample text, updating on every cursor movement.

#### Scenario: Preview updates on navigation
- **WHEN** the user moves the cursor to a new cell
- **THEN** the preview label SHALL immediately show the nick in the new cell's color

#### Scenario: Hex value shown alongside preview
- **WHEN** a cell is selected
- **THEN** the hex value of that color SHALL be displayed below the preview

### Requirement: Enter confirms and Escape cancels
Pressing Enter SHALL save the selected color to `settings.json`, update the app's in-memory nick color, and dismiss the screen. Pressing Escape SHALL dismiss without saving.

#### Scenario: Enter saves and dismisses
- **WHEN** the user navigates to a color and presses Enter
- **THEN** `nick_color` in settings SHALL be updated to the selected hex value
- **THEN** the screen SHALL be dismissed

#### Scenario: Escape dismisses without saving
- **WHEN** the user presses Escape on the color picker
- **THEN** `nick_color` SHALL remain unchanged
- **THEN** the screen SHALL be dismissed
