# Changelog — Aberrant Character Sheet

All notable changes to this project will be documented here.
Format: version — date — description

---

## [1.1.0] — 2026-05-02
### Added
- **FlightPower field** in `powers.json` — boolean added to every power; `true` for Flight, Elemental Anima, Gravity Control, Magnetic Mastery, Weather Manipulation
### Changed
- **New character defaults** — Willpower (permanent & temporary) now starts at 3; Quantum unchanged at 1
- **Initiative auto-calculated** — reads Dexterity + Wits live; shows `(+5)` when the Enhanced Initiative enhancement on Mega-Wits is ticked; field is read-only and no longer saved to the character file
- **Movement auto-calculated** — Walk = 7, Run = Dexterity + 12, Sprint = (Dexterity × 3) + 20; all update live when Dexterity changes; fields are read-only and no longer saved
- **Power cost shown beside pips** — cost (qp) is now displayed right-aligned on the same line as the rating dots in the power card header, instead of on its own row

---

## [1.0.9] — 2026-05-02
### Changed
- **Power card header** — `Qmin` value now displayed on the top-right of each power box instead of in the stat block
- **Cost line** — power cost (in qp) shown below the rating dots; permanent powers show 0 qp; Mastery techniques show the level cost when learned or double when not learned, and updates live as the proficiency checkbox is toggled
- **Dice Pool** — computed total displayed before the pool text (e.g. `6 - Quantum + Bioluminescence`); if the attribute has a Mega equivalent the mega value is shown in red in parentheses (e.g. `6 (2) - Dexterity + Quantum Blast`); all values update live when the character's attributes or power rating change

---

## [1.0.8] — 2026-05-02
### Added
- **Game Notes tab** — new full-height scrollable text area added between Quantum Powers and Portrait tabs; content saved to character file as `game_notes`
### Removed
- Description box and Experience entry removed from the Combat tab

---

## [1.0.7] — 2026-05-02
### Added
- **Quantum Powers tab** — fully functional: loads all powers from `powers.json`, picker dialog grouped by level (Mastery powers marked ★), powers displayed as cards in a 2-column layout
- Regular powers: power name, 1–5 dot rating, stat block (Quantum Min, Dice Pool, Range, Area, Duration, Multi-Action, Effect, Extras), scrollable description at bottom
- Mastery powers: same as regular plus a Techniques section — each technique has a proficiency checkbox, its own stat block, and scrollable description
- Description formatter handles `/N` (newline), `|+|` (table row break), `**text**` (section header on its own line), and first `|` (table starts on new line)
- Body Modification (Miscellaneous type) excluded from the picker
- Powers saved to and restored from character `.abe` files

---

## [1.0.6] — 2026-05-01
### Fixed
- **× button now visually removes the row** — destroy was deferred via `after(0, ...)` so the click event fully completes before the widget tree changes; applies to both custom abilities and backgrounds
- **Empty-row auto-dismiss** — clicking away from (or pressing Escape in) an empty name entry auto-removes the row without marking the character dirty; clicking `×` still works as before
### Changed
- **Backgrounds start empty** — new sheets have no pre-populated background rows
- **Background picker menu** — `+ Add Background` now opens a popup menu listing all config-defined backgrounds; choosing one adds a pre-filled row; "Custom…" adds a blank editable row

---

## [1.0.5] — 2026-05-01
### Fixed
- **Custom ability linger** — clicking `+ Add Ability` no longer marks the character dirty; empty-named rows are silently discarded on save so blank entries never reload
### Changed
- **Dynamic backgrounds** — the Backgrounds section now works like custom abilities: every entry has a name field, a dot rating, and a `×` remove button; `+ Add Background` adds new entries; existing save files load correctly into the new dynamic list

---

## [1.0.4] — 2026-05-01
### Added
- **Multi-character tabs** — `File → New Tab` (Ctrl+N) opens a fresh character; `File → Open` (Ctrl+O) loads a file into a new tab; `File → Close Tab` (Ctrl+W) closes the current tab with dirty-save prompt
- **Dynamic custom abilities** — replaced two blank fixed slots per attribute with a `+ Add Ability` button; each added row has a `×` remove button; save-file migration converts old slot format automatically
### Changed
- Endurance and Resistance now default to 3 on new character creation
- Health panel now shows the state label and penalty modifier on every row, not just the first

---

## [1.0.3] — 2026-04-28
### Added
- **Portrait tab** — load, display, and clear a character portrait image (PNG, JPEG, BMP, GIF, WebP, TIFF supported via Pillow)
- Portrait stored as base64-encoded JPEG in the character `.abe` file (capped at 300×400 px, ~30 KB)
- `app_version` field written to every saved character file
### Changed
- **Save-file migration**: opening a file missing `app_version` or `portrait` automatically adds those fields and marks the file dirty so the user is prompted to re-save

---

## [1.0.2] — 2026-04-28
### Fixed
- Second (and subsequent) specializations and enhancements no longer appear offset to the left — all entries now stack inside the same inline frame, eliminating the broken fixed-width spacer approach

---

## [1.0.1] — 2026-04-28
### Added
- Default window resolution (1300×900) defined in `aberrant_config.json`
- **Settings > Window Size…** menu to change and persist window resolution at runtime

---

## [1.0.0] — 2025-04-25
### Added
- Initial application created by Alex B and Claude
- Full character sheet UI for the Aberrant RPG system
- Attributes, Abilities, Mega-Attributes, Backgrounds, Combat, and Powers tabs
- Dot-rating widgets, specialty tracking, health level configuration
- Quantum pool, Willpower, and Taint tracking
- Save/Load character files (.abe format)
- `aberrant_config.json` for game data (attributes, abilities, specialties, enhancements)
- `powers.json` for quantum power definitions
