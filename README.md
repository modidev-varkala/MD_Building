# MD_Building

A QGIS plugin for guided orthogonal building-footprint digitizing.

## Features

- Digitizes directly into the currently active polygon layer.
- Uses the first two clicks to establish the initial edge direction.
- Constrains subsequent edges to perpendicular/parallel directions for 90-degree corners.
- Snaps the approximate final left-click onto the perpendicular guide through the starting point.
- Shows a red live outline preview.
- Right-click finishes the polygon; the created feature is selected and the tool stays active for the next building.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Alt+B` | Start MD_Building (works from anywhere in QGIS) |
| `Enter` | Finish and save the building (same as right-click) |
| `Backspace` / `Delete` / `Ctrl+Z` | Undo the last corner |
| `Esc` | Cancel the current building (press again to exit the tool) |

The start shortcut can be changed in **Settings → Keyboard Shortcuts** (search for "MD_Building").

## Install via QGIS plugin repository (recommended)

1. In QGIS: **Plugins → Manage and Install Plugins → Settings → Add...**
2. Name: `MD_Building`
3. URL: `https://raw.githubusercontent.com/modidev-varkala/MD_Building/main/plugins.xml`
4. Open the **All** tab, search for `MD_Building` and click **Install Plugin**.

## Manual installation

1. Download or clone this repository.
2. Copy the `MD_Building` folder into your QGIS profile's `python/plugins` directory.
3. Restart QGIS.
4. Enable **MD_Building** in **Plugins → Manage and Install Plugins**.
5. Select the existing polygon layer you want to digitize into and start the plugin from the toolbar or Plugins menu.

## Usage

- Left-click to add the first two points and establish the baseline.
- Continue left-clicking to add constrained corners.
- The final left-click is an approximate endpoint; when you right-click to finish, it is projected onto the 90-degree guide through the starting point.
- The feature is added to the active polygon layer and selected.

## Author

modidev

## Compatibility

QGIS 3.22 or later. Test on a copy of your data before production use.
