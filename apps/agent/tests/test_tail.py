"""The log is the bus between the call servers and the screens: every complete line, once, in order."""

import json

from clinic_agent.tail import LogTail, read_events


def _line(kind: str, **data) -> bytes:
    return (json.dumps({"t": 0.0, "kind": kind, **data}) + "\n").encode()


def test_what_is_already_there_is_history_not_news(tmp_path):
    (tmp_path / "old.jsonl").write_bytes(_line("call_started") + _line("caller", text="hello"))
    tail = LogTail(tmp_path)
    assert tail.poll() == []
    with open(tmp_path / "old.jsonl", "ab") as fh:
        fh.write(_line("agent", text="good morning"))
    assert [(c, seq, e["kind"]) for c, seq, e in tail.poll()] == [("old", 2, "agent")]


def test_a_call_that_starts_later_is_followed_from_its_first_line(tmp_path):
    tail = LogTail(tmp_path)
    (tmp_path / "new.jsonl").write_bytes(_line("call_started"))
    assert [(c, seq, e["kind"]) for c, seq, e in tail.poll()] == [("new", 0, "call_started")]
    assert tail.poll() == []


def test_a_half_written_line_waits_for_its_newline(tmp_path):
    tail = LogTail(tmp_path)
    whole = _line("caller", text="my name is")
    with open(tmp_path / "c.jsonl", "ab") as fh:
        fh.write(_line("call_started") + whole[:10])
    assert [e["kind"] for _, _, e in tail.poll()] == ["call_started"]
    with open(tmp_path / "c.jsonl", "ab") as fh:
        fh.write(whole[10:])
    assert [(seq, e["kind"]) for _, seq, e in tail.poll()] == [(1, "caller")]


def test_positions_agree_with_a_full_read_even_around_a_damaged_line(tmp_path):
    path = tmp_path / "c.jsonl"
    tail = LogTail(tmp_path)
    path.write_bytes(_line("call_started") + b"{not json}\n\n" + _line("caller", text="hi") + _line("agent", text="hello"))
    seen = tail.poll()
    assert [seq for _, seq, _ in seen] == [0, 1, 2]
    assert [e for _, _, e in seen] == read_events(path)


def test_a_folder_that_does_not_exist_yet_is_an_empty_one(tmp_path):
    assert LogTail(tmp_path / "calls").poll() == []
