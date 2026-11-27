# Pirate Chest Counter

I made this because I needed a quick way to keep track of how many chests I was opening mid-match without alt-tabbing to a notepad or running some bloated overlay that eats half my RAM. Kind of vibecoded it at first, then went down a rabbit hole optimizing the rendering so it stays locked at 60 FPS with basically zero CPU overhead.

It sits cleanly on top of your game, listens to global hotkeys while you play, and lets you customize pretty much everything about how it looks.

![Main Counter Preview](assets/preview-main.png)

## Features

- **Global Hotkeys:** Count chests without leaving your game (defaults to `F6` for +1, `F7` for Undo, `F8` for Split—all rebindable in settings).
- **Fully Customizable UI:**
  - Set any custom **wallpaper** (`cover`, `stretch`, or `contain`), use a solid color, or go **fully transparent**.
  - Pick any **font** installed on your system and customize the accent/number colors.
  - Optional **60 FPS particle overlays** (`rain`, `snow`, `sparkles`) built with cached sprites so they don't lag your game.
  - Toggleable number pop animation and decimal precision.
- **Loot Route Pace & Stats:**
  - Automatically starts a timer on your first chest of the match and shows your live **chests/min** pace.
  - Hitting **Split** logs the match, resets the counter, and shows how many chests you pulled in how many minutes.
  - Built-in **Edit Data** modal in case you misclick or forget to split, plus a one-click reset.
- **Lightweight:** Custom `QPainter` caching, debounced JSON saves, and zero heavy dependencies.

![Settings & Customization](assets/preview-settings.png)

## Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Perzi-Co/pirate-chest-counter.git](https://github.com/Perzi-Co/pirate-chest-counter.git)
   cd pirate-chest-counter
   ```

2. **Install dependencies** (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run it:**
   ```bash
   python main.py
   ```

## Default Controls

| Key | Action |
| :--- | :--- |
| `F6` | `+1 Chest` (starts match timer automatically) |
| `F7` | `Undo` (removes 1 chest from current match) |
| `F8` | `Split` (saves current match to history & resets counter) |

*Drag anywhere on the window to move it. Click `⚙` to change keybinds, themes, wallpapers, or edit your match history.*

## Project Structure

```text
├── main.py             # Entry point & global hotkey bridge
├── window.py           # Frameless overlay, cached background & counter widget
├── particles.py        # Sprite-cached 60fps particle system
├── tracker.py          # Match stats, pace timer & JSON persistence
├── settings.py         # User preferences dataclass
├── settings_dialog.py  # Customization UI, hotkey capture & data editor
└── assets/             # App icon and README screenshots
```