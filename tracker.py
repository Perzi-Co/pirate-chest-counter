import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_FILE = APP_DIR / "data" / "history.json"


@dataclass
class TrackDatChest:
    current: int = 0
    matches: list[int] = field(default_factory=list)
    match_times: list[float] = field(default_factory=list)
    current_elapsed: float = 0.0
    _active_since: float | None = field(default=None, repr=False)
    _dirty: bool = field(default=False, repr=False)
    last_split_summary: str = field(default="", repr=False)

    def __post_init__(self):
        self.load()

    @property
    def is_timing(self) -> bool:
        return self._active_since is not None

    @property
    def elapsed_seconds(self) -> float:
        total = self.current_elapsed
        if self._active_since is not None:
            total += max(0.0, time.monotonic() - self._active_since)
        return total

    def daChest(self) -> None:
        self.last_split_summary = ""
        if self._active_since is None:
            self._active_since = time.monotonic()
        self.current += 1
        self._dirty = True

    def undo(self) -> None:
        if self.current > 0:
            self.current -= 1
            if self.current == 0:
                self.current_elapsed = 0.0
                self._active_since = None
            self._dirty = True

    def split(self) -> None:
        duration = self.elapsed_seconds
        chests = self.current
        mins = duration / 60.0
        noun = "chest" if chests == 1 else "chests"
        self.last_split_summary = f"Last: {chests} {noun} in {mins:.1f} min"

        self.matches.append(chests)
        self.match_times.append(round(duration, 1))
        self.current = 0
        self.current_elapsed = 0.0
        self._active_since = None
        self._dirty = True
        self.flush()

    def reset_all(self) -> None:
        self.current = 0
        self.matches.clear()
        self.match_times.clear()
        self.current_elapsed = 0.0
        self._active_since = None
        self.last_split_summary = ""
        self._dirty = True
        self.flush()

    def set_data(self, current: int, matches: list[int]) -> None:
        self.current = max(0, int(current))
        self.matches = [max(0, int(m)) for m in matches]
        # Keep match_times aligned if matches were manually edited
        if len(self.match_times) > len(self.matches):
            self.match_times = self.match_times[: len(self.matches)]
        elif len(self.match_times) < len(self.matches):
            self.match_times.extend([0.0] * (len(self.matches) - len(self.match_times)))

        if self.current == 0:
            self.current_elapsed = 0.0
            self._active_since = None
        elif self._active_since is None:
            self._active_since = time.monotonic()

        self.last_split_summary = ""
        self._dirty = True
        self.flush()

    @property
    def total(self) -> int:
        return sum(self.matches)

    @property
    def average(self) -> float:
        return self.total / len(self.matches) if self.matches else 0.0

    def load(self) -> None:
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.current = int(data.get("current", 0))
            self.matches = [int(m) for m in data.get("matches", [])]
            raw_times = data.get("match_times", [])
            self.match_times = [float(t) for t in raw_times[: len(self.matches)]]
            if len(self.match_times) < len(self.matches):
                self.match_times.extend([0.0] * (len(self.matches) - len(self.match_times)))

            saved_elapsed = float(data.get("current_elapsed", 0.0))
            if self.current > 0:
                self.current_elapsed = max(0.0, saved_elapsed)
                self._active_since = time.monotonic()
            else:
                self.current_elapsed = 0.0
                self._active_since = None
            self._dirty = False
        except (FileNotFoundError, ValueError, TypeError, AttributeError):
            pass

    def flush(self) -> None:
        if not self._dirty and self._active_since is None:
            return
        self.save()

    def save(self) -> None:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        elapsed_snapshot = round(self.elapsed_seconds, 1) if self.current > 0 else 0.0
        payload = {
            "current": self.current,
            "matches": self.matches,
            "match_times": self.match_times,
            "current_elapsed": elapsed_snapshot,
        }
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp.replace(DATA_FILE)
        self._dirty = False