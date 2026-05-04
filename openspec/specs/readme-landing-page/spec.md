## ADDED Requirements

### Requirement: README has a centered hero section
The README SHALL open with a centered hero block containing the logo image, the project name as a heading, and a one-line tagline. The hero SHALL appear before any other content.

#### Scenario: Logo renders on GitHub
- **WHEN** a visitor opens the GitHub repository page
- **THEN** the hero image (`Art/HX1vx.jpg`) SHALL render centered above all text content

#### Scenario: Tagline visible below logo
- **WHEN** the hero block renders
- **THEN** the tagline "Real-time text and voice chat — entirely in your terminal." SHALL appear below the image

### Requirement: README displays a badge strip
The hero section SHALL include a row of shields.io badges: Python version, supported platforms, and test count.

#### Scenario: Python badge present
- **WHEN** the README renders
- **THEN** a badge indicating Python 3.13+ support SHALL be visible in the hero section

#### Scenario: Platform badge present
- **WHEN** the README renders
- **THEN** a badge indicating Linux · macOS · Windows support SHALL be visible

#### Scenario: Test count badge present
- **WHEN** the README renders
- **THEN** a badge showing the current test count (547) SHALL be visible

### Requirement: Feature sections use emoji headers
Each major feature group (Text Chat, Voice, Terminal-native UX, Self-hostable) SHALL use an emoji prefix in its section heading to aid visual scanning.

#### Scenario: Voice section has emoji
- **WHEN** the README renders
- **THEN** the Voice section heading SHALL begin with a microphone emoji

#### Scenario: Text chat section has emoji
- **WHEN** the README renders
- **THEN** the Text Chat section heading SHALL begin with a speech bubble emoji

### Requirement: Existing technical content is preserved
All slash commands, audio pipeline diagram, project structure, documentation table, requirements table, and quick-start instructions SHALL be present in the updated README.

#### Scenario: Quick-start commands unchanged
- **WHEN** a user reads the Quick Start section
- **THEN** the pip install and python -m commands SHALL be identical to the previous README

#### Scenario: Test count accurate
- **WHEN** the README references the test suite size
- **THEN** it SHALL state 547 tests

### Requirement: Art assets committed to git
The files `Art/HX1vx.jpg` and `Art/logo_large.png` SHALL be committed to the repository so that relative image references in the README resolve correctly on GitHub.

#### Scenario: Logo image loads without raw URL
- **WHEN** the README references `Art/HX1vx.jpg` via relative path
- **THEN** it SHALL render correctly on github.com without requiring an absolute CDN URL
