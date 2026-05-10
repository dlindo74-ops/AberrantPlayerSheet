# Changelog — Aberrant Character Sheet

All notable changes to this project will be documented here.
Format: version — date — description

---

## [1.4.0] — 2026-05-08
### Changed
- **Full attribute resolution in expressions** — `_resolve_stat_rich` replaces the old `_resolve_stat_text`; all nine standard attributes (Strength, Dexterity, Stamina, Perception, Intelligence, Wits, Appearance, Manipulation, Charisma) are now recognised as tokens inside `(…)` and `[…]` expression groups and substituted with the character's current attribute values, live-updating whenever the attribute dots change
- **Mega-attribute dice in expressions** — when an expression group references an attribute that has a Mega version (e.g. Mega-Stamina), the mega-attribute rating is shown in red next to the resolved base count, e.g. `7 (2)` where 2 is the current Mega-Stamina dots; updates live when the mega-attribute changes
- **Dice count styled in green with underline** — every resolved numeric result from an expression is now displayed in green (`#00cc44`) with an underline; surrounding non-expression text remains the default cream colour
- **Hover cursor on dice numbers** — moving the mouse over a resolved dice count changes the cursor to a hand (pointer), preparing the groundwork for a future dice roller
- **Arithmetic merge across groups** — when two expression groups are connected by an operator (e.g. `[Quantum x 3] + (power rating x 4)`), the groups are evaluated separately then the outer arithmetic collapses them into one green number (e.g. 24); similarly `(expr) x 50` folds into a single result
- Applies to stat fields (Range, Area, Duration, Effect) and scrollable description text in both regular power cards and Mastery technique sub-boxes

---

## [1.3.0] — 2026-05-08
### Added
- **Power variant selection — 6 more powers** — powers that require a choice at purchase now open a variant picker dialog; the card title reflects the chosen option:
  - *Absorption* (PWR009) — Energy or Kinetic; a character may hold both as separate cards
  - *Bodymorph* (PWR012) — preset forms (Stone, Metal, Liquid, Gas, Fire, Electricity, Ice, Plasma) plus a **Custom…** free-text entry; can be taken any number of times with different forms
  - *Boost* (PWR013) — the 9 core Attributes (Strength, Dexterity, Stamina, Perception, Intelligence, Wits, Appearance, Manipulation, Charisma); each Attribute can only be boosted once
  - *Holo* (PWR023) — one of the 5 senses (Sight, Hearing, Touch, Taste, Smell)
  - *Hypermovement* (PWR024) — Running, Swimming, or Flight
  - *Density Control* (PWR014) — Increase, Decrease, or Both Modes (representing the Full Control extra purchased at power acquisition)
- **`AllowCustomVariant` flag** in `powers.json` — powers with this flag are always available in the picker (never exhausted) and display a live text-entry field when "Custom…" is selected; currently used by Bodymorph
- **Body Modifications section** — dedicated "BODY MODIFICATIONS" section below the Quantum Powers grid with a separate **+ Add Body Modification** button in the tab header; picker lists all 9 book modifications with cost and description preview, plus a "Custom…" option; modifications are displayed as compact removable cards; any modification may be taken multiple times; saved to character file as `body_modifications` list
- **Aberrations section** — replaces the old free-text entry with a structured picker and card list; picker groups all aberrations by taint threshold (Low 4–5, Medium 6–7, High 8+, Mental Disorders) in a scrollable list with non-selectable group headers; selecting an entry shows its description; "Custom…" option available; aberrations displayed as compact removable cards; saved as `aberrations` list; old string-format saves are migrated automatically on load
- `Modifications` array added to PWR065 (Body Modification) in `powers.json` — 9 entries each with id, name, cost, and description
- `aberrations` data added to `aberrant_config.json` — 24 physical aberrations across 3 taint tiers plus 6 mental disorders, each with name and description
### Changed
- `_show_variant_picker` rewritten to support `AllowCustomVariant` — inline custom-entry frame appears/hides based on listbox selection; window auto-resizes; `<Return>` in the entry confirms; empty custom name refocuses the field
- **Health panel — Incapacitated/Dead penalty hidden** — the penalty column no longer shows a value next to Incapacitated or Dead health states; all other states are unaffected
- **Live stat field resolution** — stat fields (Range, Area, Duration, Effect) and the scrollable description text in power cards and technique sub-boxes that contain expressions like `(power rating x 4) + 40`, `(Quantum + power rating) meters`, or `(Quantum + Flight) x 50` are now evaluated and shown as computed numbers; the power's own name (e.g. "Flight", "Quantum Bolt") is treated as an alias for the power rating inside expressions; values update live when the power rating dots or the character's Quantum attribute change; only tokens inside `(…)` or `[…]` are substituted — bare mentions of "Quantum" outside parentheses (e.g. "costs 1 Quantum point") are left unchanged; powers with no expressions are unaffected
- **Power card column balancing** — new power cards are placed in whichever column is shorter (by pixel height) rather than strictly alternating left/right; cards of unequal height no longer cause one column to grow significantly taller than the other
### Migration
- `body_modifications` key added to new character template and migration guard; old saves without the key load cleanly
- `aberrations` migrated from string to list; non-empty old text is preserved as a single entry

---

## [1.2.0] — 2026-05-07
### Added
- **Power variant selection** — powers that require a sub-type (e.g. Elemental Anima, Elemental Mastery) now open a second "Choose element" dialog after selection; card is retitled to reflect the choice (e.g. "Fire Anima", "Water Mastery"); a character may hold the same base power multiple times with different variants as fully independent cards; cancelling the variant dialog adds nothing
- `Variants` and `VariantNameTemplate` fields added to PWR048 (Elemental Anima) and PWR049 (Elemental Mastery) in `powers.json`; structure is generic — any future power can be made variant-enabled by adding the same two fields
### Changed
- **Power extras — inline stat row** — "Extras:" is now a standard stat row in the power card alongside Range/Area/Duration/Effect, showing bought extras as comma-separated text with `+` / `−` buttons; `+` hidden when all extras are purchased; `−` hidden when none are bought; powers with multiple extras use a popup menu to choose which to add or remove
- **Power card font sizes** — text labels in power cards increased by 1 pt for improved readability
- **Health panel legend** — "Bashing" and "Lethal" labels are now right-aligned in the health track header
### Refactored
- `aberrant_sheet.py` (~2 774 lines) split into focused modules: `constants.py` (colour palette, file paths, version), `data_loader.py` (JSON I/O, migration, empty-character factory), `ui_widgets.py` (DotRow, CheckBox, ScrollFrame, helpers), `character_frame.py` (full CharacterFrame class), `app.py` (AberrantApp window/menu/notebook); `aberrant_sheet.py` is now a 4-line entry point

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
