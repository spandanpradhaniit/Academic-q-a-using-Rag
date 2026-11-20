"""Tests for input sanitization utilities."""

from app.core.sanitization import sanitize_text, sanitize_filename
from app.schemas import AskInput, SubjectInput, FeedbackInput, UserInput


def test_sanitize_text_escapes_html():
    assert "&lt;" in sanitize_text("<script>alert('xss')</script>")
    assert "<script>" not in sanitize_text("<script>alert('xss')</script>")


def test_sanitize_text_strips_script_patterns():
    result = sanitize_text("hello javascript: world")
    assert "javascript:" not in result


def test_sanitize_text_handles_none():
    assert sanitize_text(None) == ""
    assert sanitize_text("") == ""


def test_sanitize_text_preserves_safe_text():
    safe = "What is machine learning?"
    assert sanitize_text(safe) == safe


def test_sanitize_filename_strips_traversal():
    result = sanitize_filename("../../etc/passwd")
    assert ".." not in result
    assert result == "____etc_passwd"


def test_sanitize_filename_handles_empty():
    assert sanitize_filename("") == "document"
    assert sanitize_filename(None) == "document"


def test_sanitize_filename_preserves_valid():
    assert sanitize_filename("lecture-notes.pdf") == "lecture-notes.pdf"


def test_request_schemas_sanitize_user_text():
    assert "&lt;b&gt;" in UserInput(name="<b>Alex</b>", email="alex@example.com", password="password123").name
    assert "&lt;script&gt;" not in AskInput(question="What is RAG?").question
    assert "RAG" in AskInput(question="<script>RAG</script>").question
    assert "<script>" not in SubjectInput(name="Database", code="<script>DB</script>").code
    assert "javascript:" not in FeedbackInput(message_id="msg-1", rating="positive", comment="unsafe javascript:").comment
