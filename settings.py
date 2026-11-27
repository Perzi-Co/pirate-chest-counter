import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_DIR = APP_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"

@dataclass
class Settings:
    wallpaper_path: str = ""
    wallpaper_mode: str = "cover"     # cover | stretch | contain
    bg_color: str = "#0d1117"
    count_color: str = "#f2c14e"
    font_family: str = "Segoe UI"
    animation: str = "none"           # none | rain | snow | sparkles
    transparent: bool = False
    animate_count: bool = True
    decimals: bool = True
    key_add: str = "f6"
    key_undo: str = "f7"
    key_split: str = "f8"

    def load(self) -> None:
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(self, k):
                    setattr(self, k, v)
        except (FileNotFoundError, ValueError, TypeError):
            pass

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(SETTINGS_FILE)