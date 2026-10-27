import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from backend.llm.telemetry import LLMCallLogger, summarize_usage, track_llm_usage
from modules.db import execute_query


def _fake_llm(logger: LLMCallLogger, answers=("cevap",)) -> FakeListChatModel:
    return FakeListChatModel(responses=list(answers), callbacks=[logger])


def test_collector_records_purpose_and_latency():
    llm = _fake_llm(LLMCallLogger(model_name="fake-model", purpose="gap_analysis"))
    with track_llm_usage() as calls:
        llm.invoke("merhaba")

    assert len(calls) == 1
    assert calls[0]["purpose"] == "gap_analysis"
    assert calls[0]["model_name"] == "fake-model"
    assert calls[0]["latency_ms"] is not None and calls[0]["error"] is None
    assert summarize_usage(calls)["llm_calls"] == 1


def test_collector_is_scoped():
    llm = _fake_llm(LLMCallLogger(model_name="fake"), answers=("a", "b"))
    with track_llm_usage() as outer:
        llm.invoke("1")
        with track_llm_usage() as inner:
            llm.invoke("2")
    assert len(outer) == 2 and len(inner) == 1


def test_calls_with_user_are_written_to_db(user_and_session):
    user_id, session_id = user_and_session
    logger = LLMCallLogger(
        model_name="fake-model", purpose="synthesis", user_id=user_id, session_id=session_id, job_id=42
    )
    _fake_llm(logger).invoke("selam")

    row = execute_query(
        "SELECT model_name, purpose, session_id, job_id FROM model_calls WHERE user_id = ?",
        (user_id,),
        fetch="one",
    )
    assert dict(row) == {"model_name": "fake-model", "purpose": "synthesis", "session_id": session_id, "job_id": 42}


def test_errors_are_recorded():
    class Boom(FakeListChatModel):
        def _call(self, *args, **kwargs):
            raise RuntimeError("model yok")

    llm = Boom(responses=["x"], callbacks=[LLMCallLogger(model_name="m", purpose="p")])
    with track_llm_usage() as calls, pytest.raises(RuntimeError):
        llm.invoke("x")
    assert calls[0]["error"] == "model yok"


def test_get_chat_model_uses_configured_models():
    from backend.config import get_settings
    from backend.llm import get_chat_model

    settings = get_settings()
    assert get_chat_model().model_name == settings.groq_model
    assert get_chat_model(fast=True).model_name == settings.groq_fast_model
    assert isinstance(get_chat_model(purpose="x").callbacks[0], LLMCallLogger)
