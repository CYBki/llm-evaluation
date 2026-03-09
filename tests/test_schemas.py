"""Unit tests for app.schemas — validation rules."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.ingest import TraceBatchCreate, TraceCreate


class TestRegisterRequest:
    def test_valid(self):
        req = RegisterRequest(email="a@b.com", password="12345678")
        assert req.email == "a@b.com"

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="short")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="12345678")

    def test_long_password_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="x" * 129)


class TestLoginRequest:
    def test_valid(self):
        req = LoginRequest(email="a@b.com", password="test")
        assert req.email == "a@b.com"

    def test_empty_password_rejected(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="")


class TestTraceCreate:
    def test_valid_minimal(self):
        t = TraceCreate(question="Q?", answer="A.")
        assert t.contexts is None
        assert t.metadata is None

    def test_valid_with_contexts(self):
        t = TraceCreate(question="Q?", answer="A.", contexts=["c1", "c2"])
        assert len(t.contexts) == 2

    def test_empty_question_rejected(self):
        with pytest.raises(ValidationError):
            TraceCreate(question="", answer="A.")

    def test_empty_answer_rejected(self):
        with pytest.raises(ValidationError):
            TraceCreate(question="Q?", answer="")

    def test_question_max_length(self):
        with pytest.raises(ValidationError):
            TraceCreate(question="x" * 50001, answer="A.")

    def test_answer_max_length(self):
        with pytest.raises(ValidationError):
            TraceCreate(question="Q?", answer="x" * 100001)

    def test_non_https_webhook_rejected(self):
        with pytest.raises(ValidationError):
            TraceCreate(
                question="Q?",
                answer="A.",
                webhook_url="http://example.com/webhook",
            )

    def test_ip_webhook_rejected(self):
        with pytest.raises(ValidationError):
            TraceCreate(
                question="Q?",
                answer="A.",
                webhook_url="https://127.0.0.1/webhook",
            )


class TestTraceBatchCreate:
    def test_valid(self):
        batch = TraceBatchCreate(traces=[TraceCreate(question="Q?", answer="A.")])
        assert batch.traces[0].question == "Q?"

    def test_empty_batch_rejected(self):
        with pytest.raises(ValidationError):
            TraceBatchCreate(traces=[])

    def test_over_100_rejected(self):
        traces = [TraceCreate(question="Q?", answer="A.") for _ in range(101)]
        with pytest.raises(ValidationError):
            TraceBatchCreate(traces=traces)

    def test_batch_webhook_uses_same_validation_rules(self):
        with pytest.raises(ValidationError):
            TraceBatchCreate(
                traces=[TraceCreate(question="Q?", answer="A.")],
                webhook_url="https://localhost/webhook",
            )
