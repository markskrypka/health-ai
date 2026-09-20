"""Follow a folder of append-only call logs: every complete new line, once, with its line number.

The log is the bus between the servers that take calls and the screens that show them: a call server only ever
appends to `logs/calls/<call_id>.jsonl`, and whoever wants to watch reads from here. Nothing in this module writes.
"""

import json
from pathlib import Path


def read_events(path: Path) -> list[dict]:
    """Every complete, well-formed line of one log. A line still being written, or a damaged one, is left out —
    so an event's position in this list is the same number `LogTail` gives it."""
    events = []
    with open(path, "rb") as fh:
        data = fh.read()
    for raw in data[: data.rfind(b"\n") + 1].split(b"\n"):
        if event := _parse(raw):
            events.append(event)
    return events


def _parse(raw: bytes) -> dict | None:
    if not raw.strip():
        return None
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    return event if isinstance(event, dict) and "kind" in event else None


class LogTail:
    def __init__(self, folder: Path, from_start: bool = False):
        self.folder = folder
        self._offset: dict[str, int] = {}  # call_id -> bytes already handed out
        self._count: dict[str, int] = {}   # call_id -> events already handed out
        if not from_start:
            for path in self._logs():
                for _ in self._new_lines(path):  # what is already there is history, not news
                    pass

    def _logs(self) -> list[Path]:
        return sorted(self.folder.glob("*.jsonl")) if self.folder.exists() else []

    def _new_lines(self, path: Path):
        call_id = path.stem
        offset = self._offset.get(call_id, 0)
        try:
            if path.stat().st_size <= offset:
                return
            with open(path, "rb") as fh:
                fh.seek(offset)
                chunk = fh.read()
        except FileNotFoundError:
            return
        end = chunk.rfind(b"\n") + 1  # a half-written last line waits for its newline
        seq = self._count.get(call_id, 0)
        for raw in chunk[:end].split(b"\n"):
            if event := _parse(raw):
                yield call_id, seq, event
                seq += 1
        self._offset[call_id] = offset + end
        self._count[call_id] = seq

    def poll(self) -> list[tuple[str, int, dict]]:
        """(call_id, position in its log, event) for every line completed since the last poll."""
        return [item for path in self._logs() for item in self._new_lines(path)]
