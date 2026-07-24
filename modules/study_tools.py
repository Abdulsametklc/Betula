"""
Study Tools Module — Gemini backed summary / flashcards / quiz.
"""

from langchain_core.prompts import ChatPromptTemplate
import json
import re

from backend.llm import default_model_name, get_chat_model

SUMMARY_PROMPT = """
Sen bir eğitim asistanısın. Verilen metni analiz edip yapılandırılmış bir özet oluştur.

METİN:
{text}

GÖREV: Aşağıdaki formatta bir özet oluştur:

## Konu Başlığı
[Ana konu ve bağlamı]

## Temel Kavramlar
- [Kavram 1]: Açıklama
- [Kavram 2]: Açıklama

## Özet
[3-5 paragraf halinde ana fikirleri özetle]

## Önemli Noktalar
1. [Önemli nokta 1]
2. [Önemli nokta 2]

Türkçe olarak yanıt ver.
"""

FLASHCARD_PROMPT = """
Sen bir eğitim asistanısın. Verilen metinden {count} adet bilgi kartı (flashcard) oluştur.

METİN:
{text}

GÖREV: Her kart için aşağıdaki JSON formatında çıktı ver:

```json
[
  {{
    "question": "Açık ve net bir soru",
    "answer": "Kısa ve öz cevap (1-2 cümle)",
    "difficulty": "kolay" veya "orta" veya "zor"
  }}
]
```

Sadece JSON formatında yanıt ver.
"""

QUIZ_PROMPT = """
Sen bir eğitim asistanısın. Verilen metinden TAM OLARAK {count} adet sınav sorusu oluştur.
{topic_instruction}
METİN:
{text}
{avoid_instruction}
KURALLAR:
- SADECE iki soru tipi kullan: "multiple_choice" (çoktan seçmeli) ve "true_false" (doğru/yanlış).
- ASLA açık uçlu / klasik soru üretme.
- "multiple_choice" sorularında tam 4 şık ver ("options" dizisi 4 eleman), "answer" bu şıklardan BİRİYLE birebir aynı olmalı.
- "true_false" sorularında "options" mutlaka ["Doğru", "Yanlış"] olmalı ve "answer" ya "Doğru" ya da "Yanlış" olmalı.
- Sorular ve şıklar Türkçe olmalı, net ve tek doğru cevaplı olmalı.

GÖREV: Her soru için aşağıdaki JSON formatında çıktı ver:

```json
[
  {{
    "type": "multiple_choice",
    "question": "Soru metni",
    "options": ["A şıkkı", "B şıkkı", "C şıkkı", "D şıkkı"],
    "answer": "Doğru şık (options içinden biri)",
    "explanation": "Cevabın kısa açıklaması"
  }},
  {{
    "type": "true_false",
    "question": "İfade metni",
    "options": ["Doğru", "Yanlış"],
    "answer": "Doğru",
    "explanation": "Neden doğru/yanlış olduğunun kısa açıklaması"
  }}
]
```

Sadece JSON formatında yanıt ver.
"""


def extract_json_from_response(response_text):
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r"\[[\s\S]*\]", response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"JSON parse hatası: {json_str[:200]}...")
        return []


def chunk_text(text, max_chunk_size=4000):
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def generate_summary(text, model_name=None):
    try:
        if len(text) > 60000:
            text = text[:60000] + "\n\n[Metin kısaltıldı...]"

        prompt = ChatPromptTemplate.from_template(SUMMARY_PROMPT)
        llm = get_chat_model(temperature=0.3, model_name=model_name)
        chain = prompt | llm
        response = chain.invoke({"text": text})
        return response.content
    except Exception as e:
        return f"Özet oluşturulurken hata: {e}"


def generate_flashcards(text, count=10, model_name=None):
    try:
        if len(text) > 50000:
            text = text[:50000]

        prompt = ChatPromptTemplate.from_template(FLASHCARD_PROMPT)
        llm = get_chat_model(temperature=0.2, model_name=model_name)
        chain = prompt | llm
        response = chain.invoke({"text": text, "count": count})
        flashcards = extract_json_from_response(response.content)

        valid_cards = []
        for card in flashcards:
            if isinstance(card, dict) and "question" in card and "answer" in card:
                valid_cards.append(
                    {
                        "question": card["question"],
                        "answer": card["answer"],
                        "difficulty": card.get("difficulty", "orta"),
                    }
                )
        return valid_cards
    except Exception as e:
        print(f"Flashcard oluşturma hatası: {e}")
        return []


def _normalize_quiz_question(q: dict) -> dict | None:
    """LLM ciktisini coktan secmeli / dogru-yanlis formatina normalize eder."""
    if not isinstance(q, dict) or "question" not in q or "answer" not in q:
        return None

    raw_type = str(q.get("type", "")).lower()
    options = q.get("options") or []
    if not isinstance(options, list):
        options = []
    options = [str(o).strip() for o in options if str(o).strip()]

    answer = str(q["answer"]).strip()

    # Dogru/Yanlis tespiti
    tf_markers = {"true_false", "doğru_yanlış", "dogru_yanlis", "true/false", "tf"}
    is_tf = raw_type in tf_markers or (
        len(options) == 2
        and {o.lower() for o in options} <= {"doğru", "yanlış", "dogru", "yanlis", "true", "false"}
    )

    if is_tf:
        low = answer.lower()
        if low in ("doğru", "dogru", "true", "d", "evet"):
            answer = "Doğru"
        elif low in ("yanlış", "yanlis", "false", "y", "hayır", "hayir"):
            answer = "Yanlış"
        else:
            return None
        return {
            "type": "true_false",
            "question": str(q["question"]).strip(),
            "options": ["Doğru", "Yanlış"],
            "answer": answer,
            "explanation": str(q.get("explanation", "")).strip(),
        }

    # Coktan secmeli: en az 2 sik
    if len(options) < 2:
        return None

    # Cevabi siklara eslestir (metin / harf / "A) ..." formatlari)
    matched = next((o for o in options if o.lower() == answer.lower()), None)
    if not matched:
        # "A", "B", "C", "D" veya "A)" / "A." gibi harf cevaplari
        letter = re.match(r"^([A-Da-d])(?:[\)\.\:]|$)", answer)
        if letter:
            idx = ord(letter.group(1).upper()) - ord("A")
            if 0 <= idx < len(options):
                matched = options[idx]
        else:
            # Cevap bir sikkin baslangiciysa
            matched = next(
                (o for o in options if o.lower().startswith(answer.lower()) or answer.lower() in o.lower()),
                None,
            )
    if not matched:
        return None

    # 4 siktan fazla ise ilk 4'e kirp, cevabi koru
    if len(options) > 4:
        if matched in options[:4]:
            options = options[:4]
        else:
            options = options[:3] + [matched]

    return {
        "type": "multiple_choice",
        "question": str(q["question"]).strip(),
        "options": options,
        "answer": matched,
        "explanation": str(q.get("explanation", "")).strip(),
    }


def _invoke_quiz_batch(text, count, model_name, topic_instruction, avoid_instruction, avoid_set):
    """Tek bir LLM cagrisindan gecerli sorulari cikarir."""
    prompt = ChatPromptTemplate.from_template(QUIZ_PROMPT)
    llm = get_chat_model(temperature=0.45, model_name=model_name)
    chain = prompt | llm
    response = chain.invoke(
        {
            "text": text,
            "count": count,
            "topic_instruction": topic_instruction,
            "avoid_instruction": avoid_instruction,
        }
    )
    questions = extract_json_from_response(response.content)
    valid = []
    seen = set(avoid_set)
    for q in questions:
        norm = _normalize_quiz_question(q)
        if not norm:
            continue
        key = norm["question"].lower()
        if key in seen:
            continue
        seen.add(key)
        valid.append(norm)
    return valid


def generate_quiz(text, count=10, model_name=None, topic=None, avoid_questions=None):
    """Istenen sayida gecerli soru uretir; eksik kalirsa 1 kez tamamlar."""
    try:
        if len(text) > 50000:
            text = text[:50000]

        topic_instruction = ""
        if topic and topic.strip():
            topic_instruction = (
                f'ODAK KONU: Sorular SADECE "{topic.strip()}" konusuyla ilgili olsun. '
                "Bu konu metinde yoksa metindeki en yakin bilgiden yararlan.\n"
            )

        avoid_list = [str(a).strip() for a in (avoid_questions or []) if str(a).strip()]
        avoid_set = {a.lower() for a in avoid_list}

        def _avoid_block(extra=None):
            sample = (avoid_list + (extra or []))[:50]
            if not sample:
                return ""
            joined = "\n".join(f"- {s}" for s in sample)
            return (
                "\nDAHA ONCE SORULAN SORULAR (bunlari TEKRAR ETME, farkli sorular uret):\n"
                f"{joined}\n"
            )

        # Biraz fazla iste: normalize/dedup kayiplarina tampon
        ask = count + 2
        valid = _invoke_quiz_batch(
            text, ask, model_name, topic_instruction, _avoid_block(), avoid_set
        )

        # Eksikse bir tur daha tamamla
        if len(valid) < count:
            need = count - len(valid) + 1
            already = [v["question"] for v in valid]
            more = _invoke_quiz_batch(
                text,
                need,
                model_name,
                topic_instruction,
                _avoid_block(already),
                avoid_set | {v["question"].lower() for v in valid},
            )
            valid.extend(more)

        return valid[:count]
    except Exception as e:
        print(f"Sınav sorusu oluşturma hatası: {e}")
        return []


def generate_study_material(
    text,
    document_id,
    model_name=None,
    generate_summary_=True,
    flashcard_count=10,
    quiz_count=10,
    user_id=None,
):
    if user_id is None:
        raise ValueError("Security Error: generate_study_material requires user_id parameter")

    from modules.repo_documents import (
        create_summary,
        create_flashcards_bulk,
        create_quiz_questions_bulk,
        mark_document_processed,
    )

    model_name = model_name or default_model_name()
    results = {"summary": None, "flashcards": [], "quiz_questions": []}

    try:
        if generate_summary_:
            summary = generate_summary(text, model_name)
            if summary and not summary.startswith("Özet oluşturulurken hata"):
                create_summary(document_id, summary, user_id=user_id)
                results["summary"] = summary

        if flashcard_count > 0:
            flashcards = generate_flashcards(text, flashcard_count, model_name)
            if flashcards:
                create_flashcards_bulk(flashcards, user_id=user_id, document_id=document_id)
                results["flashcards"] = flashcards

        if quiz_count > 0:
            questions = generate_quiz(text, quiz_count, model_name)
            if questions:
                create_quiz_questions_bulk(questions, user_id=user_id, document_id=document_id)
                results["quiz_questions"] = questions

        mark_document_processed(document_id, user_id=user_id)
    except Exception as e:
        print(f"Materyal oluşturma hatası: {e}")

    return results
