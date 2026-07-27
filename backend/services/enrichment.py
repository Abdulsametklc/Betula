"""
Chat enrichment: konuyla ilgili ama belgede olmayan soruları
web'den araştırıp cevaplar; Master Sentez'e Ek Bilgiler olarak ekler.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.llm import get_chat_model
from backend.services.vectorstore import add_to_vector_db
from modules.repo_pipeline import append_ek_bilgi_to_compiled_note, get_compiled_note_for_document

ASSESS_PROMPT = """Sen bir egitim asistanisin. Kullanici sorusunu ve belge baglamini degerlendir.

SORU:
{question}

BELGE BAGLAMI (ozet parcalar):
{context}

SADECE JSON dondur:
{{
  "on_topic": true/false,
  "covered": true/false,
  "topic": "kisa konu basligi",
  "search_query": "web arama sorgusu (Turkce veya Ingilizce)"
}}

KURALLAR:
- on_topic: soru bu calisma notlari / belge konusuyla ilgili mi?
- covered: baglamda soruyu dogrudan ve yeterli cevaplayacak bilgi VAR mi?
- Konuyla ilgili ama baglamda yoksa: on_topic=true, covered=false
- Selamlama, genel sohbet, tamamen alakasiz soru: on_topic=false
"""

ANSWER_FROM_RESEARCH_PROMPT = """Sen Betula egitim asistanisin. Kullanici sorusu belgede yoktu; web arastirmasi yaptin.
Turkce, net ve egitici bir cevap ver. Uydurma yapma; sadece arastirma sonucuna dayan.

SORU: {question}

WEB ARASTIRMASI:
{research}

KURALLAR:
- SADECE TURKCE
- Formuller, tanimlar, adimlar varsa acik yaz
- Sonunda kisa bir not ekle: "Bu bilgi kaynaklarinda yoktu; arastirilarak eklendi."
"""


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _ddg_search(query: str, max_results: int = 4) -> list[dict]:
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


def assess_coverage(*, question: str, context: str) -> dict[str, Any]:
    """Soru belge konusuyla ilgili mi ve baglamda cevap var mi?"""
    ctx = (context or "").strip()
    if not ctx or len(ctx) < 40:
        # Baglam yoksa arastirma yapma; genel sohbet kalsin
        return {
            "on_topic": False,
            "covered": False,
            "topic": "",
            "search_query": question[:120],
        }

    llm = get_chat_model(temperature=0.0, fast=True)
    response = llm.invoke(
        ASSESS_PROMPT.format(question=question[:800], context=ctx[:8000])
    )
    content = response.content if hasattr(response, "content") else str(response)
    data = _parse_json_object(content)
    return {
        "on_topic": bool(data.get("on_topic")),
        "covered": bool(data.get("covered")),
        "topic": str(data.get("topic") or question[:80]).strip(),
        "search_query": str(data.get("search_query") or question[:120]).strip(),
    }


def research_and_answer(*, question: str, search_query: str, topic: str) -> dict[str, Any]:
    """Web ara + LLM cevabi uret."""
    hits = _ddg_search(search_query or question, max_results=4)
    results_text = "\n\n".join(
        f"- {h.get('title')}: {h.get('body')} ({h.get('href')})" for h in hits
    )
    llm = get_chat_model(temperature=0.2, fast=True)
    response = llm.invoke(
        ANSWER_FROM_RESEARCH_PROMPT.format(
            question=question,
            research=results_text or "Sonuc yok",
        )
    )
    answer = response.content if hasattr(response, "content") else str(response)
    # Ozet: cevabin ilk paragraflari (ek LLM cagrisi yok — kota dostu)
    paras = [p.strip() for p in str(answer).split("\n\n") if p.strip()]
    summary_text = "\n\n".join(paras[:2]) if paras else str(answer)[:500]
    return {
        "answer": answer,
        "summary": summary_text,
        "topic": topic,
        "sources": hits,
        "search_query": search_query,
    }


def persist_ek_bilgi(
    *,
    user_id: int,
    document_id: int | None,
    session_id: int | None,
    topic: str,
    summary: str,
    answer: str,
    sources: list[dict],
    question: str,
) -> bool:
    """Master Sentez'e Ek Bilgiler ekler + FAISS'e indeksler."""
    if not document_id:
        return False

    block = (
        f"### {topic}\n\n"
        f"**Soru:** {question}\n\n"
        f"{summary.strip()}\n\n"
        f"<details><summary>Detayli cevap</summary>\n\n{answer.strip()}\n\n</details>\n"
    )
    if sources:
        links = "\n".join(
            f"- [{s.get('title') or s.get('href')}]({s.get('href')})"
            for s in sources
            if s.get("href")
        )
        if links:
            block += f"\n**Kaynaklar:**\n{links}\n"

    gap_item = {
        "topic": topic,
        "reason": "Sohbette soruldu; belgede yoktu, arastirilarak eklendi.",
        "search_query": question,
        "summary": summary,
        "sources": sources,
        "from_chat": True,
    }

    ok = append_ek_bilgi_to_compiled_note(
        user_id=user_id,
        document_id=document_id,
        session_id=session_id,
        markdown_block=block,
        gap_item=gap_item,
    )

    try:
        index_text = f"{topic}\n\n{question}\n\n{summary}\n\n{answer}"
        add_to_vector_db(index_text, user_id=user_id, session_id=session_id)
    except Exception as e:
        print(f"Ek bilgi vectorstore hatasi: {e}")

    return ok


def try_enrich_from_chat(
    *,
    question: str,
    context: str,
    user_id: int,
    document_id: int | None,
    session_id: int | None,
) -> dict[str, Any] | None:
    """
    Konuyla ilgili ama belgede yoksa arastirip cevap + not guncellemesi dondurur.
    Arastirma gerekmezse None.
    """
    assessment = assess_coverage(question=question, context=context)
    if not assessment.get("on_topic") or assessment.get("covered"):
        return None

    researched = research_and_answer(
        question=question,
        search_query=assessment.get("search_query") or question,
        topic=assessment.get("topic") or "Ek bilgi",
    )
    note_updated = persist_ek_bilgi(
        user_id=user_id,
        document_id=document_id,
        session_id=session_id,
        topic=researched["topic"],
        summary=researched["summary"],
        answer=researched["answer"],
        sources=researched["sources"],
        question=question,
    )
    return {
        **researched,
        "note_updated": note_updated,
        "assessment": assessment,
    }
