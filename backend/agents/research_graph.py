"""
LangGraph research pipeline:
Parse → GapAnalysis → WebResearch → Synthesis → Persist
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.config import get_settings
from backend.llm import get_chat_model
from backend.services.vectorstore import create_vector_db
from modules.repo_documents import get_document, mark_document_processed
from modules.repo_pipeline import save_compiled_note, update_pipeline_job


class PipelineState(TypedDict, total=False):
    user_id: int
    document_id: int
    job_id: int
    session_id: int
    text: str
    outline: str
    gaps: list
    research: list
    markdown: str
    sources: list
    error: str


GAP_PROMPT = """Sen bir egitim diagnostik asistanisin.
Asagidaki calisma notlarini oku. Hangi konular karmasik veya yarim birakilmis?
Hangi terimlerin aciklamasi eksik? Arastirilmasi gereken eksik basliklarin bir listesini ver.

NOTLAR:
{text}

SADECE JSON dondur:
{{
  "outline": "kisa taslak ozeti",
  "gaps": [
    {{"topic": "baslik", "reason": "neden eksik", "search_query": "web arama sorgusu"}}
  ]
}}

En fazla {max_gaps} gap uret. Turkce yaz.
"""

RESEARCH_SUMMARY_PROMPT = """Asagidaki web arama sonuclarini kullanarak "{topic}" konusunu
ogrenci icin net ve anlasilir sekilde ozetle (Turkce, 1-2 kisa paragraf).

ARAMA SONUCLARI:
{results}
"""

SYNTHESIS_PROMPT = """Sen Betula egitim asistanisin.
Orijinal ogrenci notlari ile web arastirmasini harmanla.
Hiyerarsik, eksiksiz, okumasi keyifli bir Markdown "Kusursuz Calisma Notu" uret.

KURALLAR:
- Turkce yaz
- Basliklar, alt basliklar, onemli uyarilar kullan
- Kaynaklardan gelen bilgileri notlarla birlestir; uydurma yapma
- Sonunda "Eksiklerden Tamamlanan Konular" bolumu ekle

ORIJINAL NOTLAR:
{text}

WEB ARASTIRMASI:
{research}
"""


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _set_step(state: PipelineState, step: str, status: str = "running") -> None:
    update_pipeline_job(
        state["job_id"],
        user_id=state["user_id"],
        status=status,
        current_step=step,
    )


def node_parse(state: PipelineState) -> PipelineState:
    _set_step(state, "parse")
    doc = get_document(state["document_id"], user_id=state["user_id"])
    if not doc or not doc.get("content"):
        return {**state, "error": "Dokuman bulunamadi veya bos"}
    text = doc["content"]
    # Groq context-safe trim (~chars; models ~128k tokens)
    if len(text) > 60_000:
        text = text[:60_000] + "\n\n[Metin kisaltildi...]"
    session_id = state.get("session_id") or doc.get("session_id")
    return {**state, "text": text, "session_id": session_id}


def node_gap_analysis(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    _set_step(state, "gap_analysis")
    settings = get_settings()
    llm = get_chat_model(temperature=0.1)
    prompt = GAP_PROMPT.format(text=state["text"][:40_000], max_gaps=settings.max_gaps)
    response = llm.invoke(prompt)
    data = _parse_json_object(response.content or "")
    gaps = data.get("gaps") or []
    if not isinstance(gaps, list):
        gaps = []
    gaps = gaps[: settings.max_gaps]
    outline = data.get("outline") or ""
    return {**state, "gaps": gaps, "outline": outline}


def _ddg_search(query: str, max_results: int = 3) -> list[dict]:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "body": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": "search_error", "href": "", "body": str(e)}]


def _research_one_gap(gap: dict) -> dict[str, Any]:
    """Tek bir gap icin arama + LLM ozeti (thread-safe; her cagri kendi LLM istemcisini acar)."""
    topic = gap.get("topic") or gap.get("search_query") or "konu"
    query = gap.get("search_query") or topic
    hits = _ddg_search(query, max_results=3)
    results_text = "\n\n".join(
        f"- {h.get('title')}: {h.get('body')} ({h.get('href')})" for h in hits
    )
    llm = get_chat_model(temperature=0.2, fast=True)
    summary = llm.invoke(
        RESEARCH_SUMMARY_PROMPT.format(topic=topic, results=results_text or "Sonuc yok")
    )
    return {
        "topic": topic,
        "reason": gap.get("reason", ""),
        "summary": summary.content if hasattr(summary, "content") else str(summary),
        "sources": hits,
    }


def node_web_research(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    _set_step(state, "web_research")
    settings = get_settings()

    # Her gap araştırılsın — max_gaps ile max_web_searches uyumsuzsa eksik özet kalmasın
    limit = max(1, min(settings.max_gaps, settings.max_web_searches))
    gaps = (state.get("gaps") or [])[:limit]
    if not gaps:
        return {**state, "research": [], "sources": [], "gaps": []}

    research: list[dict[str, Any]] = [None] * len(gaps)  # type: ignore[list-item]
    # Groq TPM için paralelizmi sınırlı tut; yine de tüm gap'ler tamamlanır
    workers = min(len(gaps), 3)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(_research_one_gap, gap): i for i, gap in enumerate(gaps)}
        for fut in as_completed(future_map):
            idx = future_map[fut]
            try:
                research[idx] = fut.result()
            except Exception as e:
                gap = gaps[idx]
                topic = gap.get("topic") or gap.get("search_query") or "konu"
                research[idx] = {
                    "topic": topic,
                    "reason": gap.get("reason", ""),
                    "summary": f"Arastirma hatasi: {e}",
                    "sources": [],
                }

    sources: list[dict[str, Any]] = []
    for item in research:
        if not item:
            continue
        sources.extend(item.get("sources") or [])

    # UI'da yalnızca araştırılan gap'ler görünsün (araştırılmayan boş başlık kalmasın)
    return {**state, "gaps": gaps, "research": research, "sources": sources}


def node_synthesis(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    _set_step(state, "synthesis")
    llm = get_chat_model(temperature=0.3)
    research_blob = json.dumps(state.get("research") or [], ensure_ascii=False, indent=2)
    response = llm.invoke(
        SYNTHESIS_PROMPT.format(text=state["text"][:35_000], research=research_blob)
    )
    markdown = response.content if hasattr(response, "content") else str(response)
    return {**state, "markdown": markdown}


def node_persist(state: PipelineState) -> PipelineState:
    if state.get("error"):
        update_pipeline_job(
            state["job_id"],
            user_id=state["user_id"],
            status="failed",
            current_step="failed",
            error=state["error"],
        )
        return state

    _set_step(state, "persist")
    markdown = state.get("markdown") or ""

    # Gap'leri web arastirma ozetleriyle birlestir - UI bunlari ekranda gosterir
    research_by_topic = {r.get("topic"): r for r in (state.get("research") or [])}
    enriched_gaps = []
    for gap in state.get("gaps") or []:
        topic = gap.get("topic") or gap.get("search_query") or "konu"
        found = research_by_topic.get(topic) or {}
        enriched_gaps.append(
            {
                "topic": topic,
                "reason": gap.get("reason", ""),
                "search_query": gap.get("search_query", ""),
                "summary": found.get("summary", ""),
                "sources": found.get("sources", []),
            }
        )

    gap_list_json = json.dumps(enriched_gaps, ensure_ascii=False)
    sources_json = json.dumps(state.get("sources") or [], ensure_ascii=False)

    save_compiled_note(
        user_id=state["user_id"],
        document_id=state["document_id"],
        markdown=markdown,
        gap_list_json=gap_list_json,
        sources_json=sources_json,
        status="done",
        session_id=state.get("session_id"),
    )

    # Index compiled note + original text for RAG
    index_text = (state.get("text") or "") + "\n\n" + markdown
    create_vector_db(
        index_text,
        user_id=state["user_id"],
        persist=True,
        session_id=state.get("session_id"),
    )
    mark_document_processed(state["document_id"], user_id=state["user_id"])

    update_pipeline_job(
        state["job_id"],
        user_id=state["user_id"],
        status="done",
        current_step="done",
        error="",
    )
    return state


def build_research_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("parse", node_parse)
    graph.add_node("gap_analysis", node_gap_analysis)
    graph.add_node("web_research", node_web_research)
    graph.add_node("synthesis", node_synthesis)
    graph.add_node("persist", node_persist)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "gap_analysis")
    graph.add_edge("gap_analysis", "web_research")
    graph.add_edge("web_research", "synthesis")
    graph.add_edge("synthesis", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


_compiled_graph = None


def get_research_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_research_graph()
    return _compiled_graph


def run_research_pipeline(*, user_id: int, document_id: int, job_id: int, session_id: int | None = None) -> dict:
    graph = get_research_graph()
    initial: PipelineState = {
        "user_id": user_id,
        "document_id": document_id,
        "job_id": job_id,
    }
    if session_id:
        initial["session_id"] = session_id
    try:
        update_pipeline_job(job_id, user_id=user_id, status="running", current_step="parse")
        result = graph.invoke(initial)
        if result.get("error"):
            update_pipeline_job(
                job_id,
                user_id=user_id,
                status="failed",
                current_step="failed",
                error=result["error"],
            )
        return result
    except Exception as e:
        update_pipeline_job(
            job_id,
            user_id=user_id,
            status="failed",
            current_step="failed",
            error=str(e),
        )
        return {**initial, "error": str(e)}
