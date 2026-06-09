import pytest
from widget.services.clipboard_reader import ClipboardReader, MAX_CHARS


def test_read_returns_clipboard_text():
    reader = ClipboardReader(get_clipboard=lambda: "タスクを確認する")
    assert reader.read() == "タスクを確認する"


def test_read_truncates_long_text():
    long_text = "a" * (MAX_CHARS + 100)
    reader = ClipboardReader(get_clipboard=lambda: long_text)
    result = reader.read()
    assert len(result) == MAX_CHARS


def test_read_returns_empty_on_exception():
    def raise_error() -> str:
        raise Exception("clipboard empty")
    reader = ClipboardReader(get_clipboard=raise_error)
    assert reader.read() == ""


def test_has_content_returns_true_when_text_present():
    reader = ClipboardReader(get_clipboard=lambda: "some text")
    assert reader.has_content() is True


def test_has_content_returns_false_when_empty():
    reader = ClipboardReader(get_clipboard=lambda: "")
    assert reader.has_content() is False
