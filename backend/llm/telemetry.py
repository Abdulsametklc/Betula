"""LLM cagri telemetrisi: her cagrinin amaci, modeli, token sayisi ve suresi.

Kayitlar uc yere gider:
- Python logger (``betula.llm``) — sunucu loglari
- ``model_calls`` tablosu — ``user_id`` biliniyorsa (maliyet / gecikme analizi)
- ``track_llm_usage()`` ile acilan toplayicilar — degerlendirme betikleri icin
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

log = logging.getLogger("betula.llm")

_collectors: ContextVar[tuple[list, ...]] = ContextVar("llm_usage_collectors", default=())


@contextmanager
def track_llm_usage() -> Iterator[list[dict]]:
    """Blok icindeki (ayni thread) tum LLM cagrilarinin kayitlarini toplar."""
    records: list[dict] = []
    token = _collectors.set(_collectors.get() + (records,))
    try:
        yield records
    finally:
        _collectors.reset(token)


def summarize_usage(records: list[dict]) -> dict:
    def total(key: str) -> int:
        return sum(r.get(key) or 0 for r in records)

    return {
        "llm_calls": len(records),
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "llm_latency_ms": total("latency_ms"),
        "llm_errors": sum(1 for r in records if r.get("error")),
    }


def _usage_from_result(response: LLMResult) -> tuple[Optional[int], Optional[int]]:
    for generations in response.generations or []:
        for gen in generations:
            usage = getattr(getattr(gen, "message", None), "usage_metadata", None)
            if usage:
                return usage.get("input_tokens"), usage.get("output_tokens")
    token_usage = (response.llm_output or {}).get("token_usage") or {}
    return token_usage.get("prompt_tokens"), token_usage.get("completion_tokens")


class LLMCallLogger(BaseCallbackHandler):
    """``get_chat_model`` tarafindan her istemciye eklenen callback."""

    def __init__(
        self,
        *,
        model_name: str,
        purpose: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        job_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        self.model_name = model_name
        self.purpose = purpose
        self.user_id = user_id
        self.session_id = session_id
        self.job_id = job_id
        self.conversation_id = conversation_id
        self._started: dict[UUID, float] = {}

    def on_chat_model_start(self, serialized: Any, messages: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._started[run_id] = time.perf_counter()

    def on_llm_start(self, serialized: Any, prompts: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._started[run_id] = time.perf_counter()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        prompt_tokens, completion_tokens = _usage_from_result(response)
        self._record(run_id, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._record(run_id, error=str(error)[:500])

    def _record(self, run_id: UUID, **fields: Any) -> None:
        started = self._started.pop(run_id, None)
        record = {
            "model_name": self.model_name,
            "purpose": self.purpose,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "job_id": self.job_id,
            "conversation_id": self.conversation_id,
            "latency_ms": int((time.perf_counter() - started) * 1000) if started else None,
            "prompt_tokens": fields.get("prompt_tokens"),
            "completion_tokens": fields.get("completion_tokens"),
            "error": fields.get("error"),
        }
        for records in _collectors.get():
            records.append(record)
        log.info(
            "llm purpose=%s model=%s in=%s out=%s ms=%s%s",
            record["purpose"], record["model_name"], record["prompt_tokens"],
            record["completion_tokens"], record["latency_ms"],
            f" error={record['error']}" if record["error"] else "",
        )
        if self.user_id is not None:
            try:
                from modules.repo_chat import log_model_call

                log_model_call(
                    record["model_name"],
                    user_id=self.user_id,
                    conversation_id=self.conversation_id,
                    prompt_tokens=record["prompt_tokens"],
                    completion_tokens=record["completion_tokens"],
                    latency_ms=record["latency_ms"],
                    error=record["error"],
                    purpose=self.purpose,
                    session_id=self.session_id,
                    job_id=self.job_id,
                )
            except Exception as e:  # telemetri asla asil isi bozmamali
                log.warning("model_calls yazilamadi: %s", e)
