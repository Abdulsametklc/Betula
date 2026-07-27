"""
Chat Repository - Multi-Tenant Ready
=====================================
Conversation ve Message CRUD islemleri.
Her fonksiyon user_id ile calisir - veri izolasyonu garanti.
"""

from typing import Optional
from .db import get_db, require_user_id, execute_query


# ============== CONVERSATION FONKSIYONLARI ==============

@require_user_id
def create_conversation(*, user_id: int, title: str = "Yeni Sohbet", model_name: str = "qwen2.5:7b", session_id: int = None) -> int:
    """Yeni sohbet oturumu olusturur."""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO conversations (user_id, session_id, title, model_name) 
               VALUES (?, ?, ?, ?)""",
            (user_id, session_id, title, model_name)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def list_conversations(*, user_id: int, session_id: int = None, limit: int = 50) -> list:
    """Kullanicinin sohbetlerini listeler (onizleme + mesaj sayisi ile)."""
    base = """
        SELECT c.id, c.title, c.model_name, c.created_at, c.updated_at, c.session_id,
               (SELECT m.content FROM messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.id DESC LIMIT 1) AS last_message,
               (SELECT COUNT(*) FROM messages m
                WHERE m.conversation_id = c.id) AS message_count
        FROM conversations c
        WHERE c.user_id = ?
    """
    if session_id:
        return execute_query(
            base + " AND c.session_id = ? ORDER BY c.updated_at DESC LIMIT ?",
            (user_id, session_id, limit),
            fetch="all",
        )
    return execute_query(
        base + " ORDER BY c.updated_at DESC LIMIT ?",
        (user_id, limit),
        fetch="all",
    )


@require_user_id
def get_conversation(conversation_id: int, *, user_id: int) -> Optional[dict]:
    """Belirli bir sohbeti getirir - user_id kontrolu ile.
    
    GUVENLIK: Baska kullanicinin conversation'ina erisim engellenir.
    
    Args:
        conversation_id: Sohbet ID
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Conversation dict veya None
    """
    return execute_query(
        """SELECT id, title, model_name, created_at, updated_at, session_id 
           FROM conversations 
           WHERE id = ? AND user_id = ?""",
        (conversation_id, user_id),
        fetch='one'
    )


@require_user_id
def update_conversation(conversation_id: int, *, user_id: int, title: str = None, model_name: str = None) -> bool:
    """Sohbet bilgilerini gunceller.
    
    Args:
        conversation_id: Sohbet ID
        user_id: Kullanici ID (zorunlu keyword arg)
        title: Yeni baslik (opsiyonel)
        model_name: Yeni model (opsiyonel)
        
    Returns:
        True eger guncelleme basarili ise
    """
    updates = []
    params = []
    
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    
    if model_name is not None:
        updates.append("model_name = ?")
        params.append(model_name)
    
    if not updates:
        return False
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([conversation_id, user_id])
    
    with get_db() as conn:
        cursor = conn.execute(
            f"""UPDATE conversations 
                SET {', '.join(updates)} 
                WHERE id = ? AND user_id = ?""",
            params
        )
        conn.commit()
        return cursor.rowcount > 0


@require_user_id
def delete_conversation(conversation_id: int, *, user_id: int) -> bool:
    """Sohbeti ve tum mesajlarini siler.
    
    Args:
        conversation_id: Sohbet ID
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        True eger silme basarili ise
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# ============== MESSAGE FONKSIYONLARI ==============

@require_user_id
def create_message(conversation_id: int, role: str, content: str, *, user_id: int) -> int:
    """Yeni mesaj olusturur.
    
    GUVENLIK: conversation'in user'a ait oldugu kontrol edilir.
    
    Args:
        conversation_id: Sohbet ID
        role: 'user', 'assistant', veya 'system'
        content: Mesaj icerigi
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Yeni message_id
        
    Raises:
        ValueError: Conversation kullaniciya ait degilse
    """
    # Once conversation'in bu user'a ait oldugunu kontrol et
    conv = get_conversation(conversation_id, user_id=user_id)
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found or access denied")
    
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO messages (conversation_id, user_id, role, content) 
               VALUES (?, ?, ?, ?)""",
            (conversation_id, user_id, role, content)
        )
        # Conversation updated_at guncelle
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_messages(conversation_id: int, *, user_id: int, limit: int = 100) -> list:
    """Sohbetin mesajlarini getirir - user_id kontrolu ile.
    
    GUVENLIK: Baska kullanicinin mesajlarina erisim engellenir.
    
    Args:
        conversation_id: Sohbet ID
        user_id: Kullanici ID (zorunlu keyword arg)
        limit: Maksimum mesaj sayisi
        
    Returns:
        Message listesi (dict)
    """
    return execute_query(
        """SELECT id, role, content, created_at 
           FROM messages 
           WHERE conversation_id = ? AND user_id = ?
           ORDER BY created_at ASC
           LIMIT ?""",
        (conversation_id, user_id, limit),
        fetch='all'
    )


@require_user_id  
def get_recent_messages(*, user_id: int, limit: int = 50) -> list:
    """Kullanicinin son mesajlarini getirir (tum sohbetlerden).
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        limit: Maksimum mesaj sayisi
        
    Returns:
        Message listesi (dict) - conversation bilgisi ile
    """
    return execute_query(
        """SELECT m.id, m.role, m.content, m.created_at,
                  c.id as conversation_id, c.title as conversation_title
           FROM messages m
           JOIN conversations c ON m.conversation_id = c.id
           WHERE m.user_id = ?
           ORDER BY m.created_at DESC
           LIMIT ?""",
        (user_id, limit),
        fetch='all'
    )


@require_user_id
def search_messages(query: str, *, user_id: int, limit: int = 20) -> list:
    """Mesajlarda arama yapar.
    
    Args:
        query: Arama terimi
        user_id: Kullanici ID (zorunlu keyword arg)
        limit: Maksimum sonuc sayisi
        
    Returns:
        Eslesen mesajlar
    """
    return execute_query(
        """SELECT m.id, m.role, m.content, m.created_at,
                  c.id as conversation_id, c.title as conversation_title
           FROM messages m
           JOIN conversations c ON m.conversation_id = c.id
           WHERE m.user_id = ? AND m.content LIKE ?
           ORDER BY m.created_at DESC
           LIMIT ?""",
        (user_id, f"%{query}%", limit),
        fetch='all'
    )


# ============== TELEMETRY FONKSIYONLARI ==============

@require_user_id
def log_model_call(
    model_name: str,
    *,
    user_id: int,
    conversation_id: int = None,
    prompt_tokens: int = None,
    completion_tokens: int = None,
    latency_ms: int = None,
    error: str = None
) -> int:
    """Model cagrisini loglar (telemetry).
    
    Args:
        model_name: Kullanilan model
        user_id: Kullanici ID (zorunlu keyword arg)
        conversation_id: Ilgili sohbet (opsiyonel)
        prompt_tokens: Prompt token sayisi
        completion_tokens: Yanit token sayisi
        latency_ms: Yanit suresi (ms)
        error: Hata mesaji (varsa)
        
    Returns:
        Log ID
    """
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO model_calls 
               (user_id, conversation_id, model_name, prompt_tokens, 
                completion_tokens, latency_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, conversation_id, model_name, prompt_tokens, 
             completion_tokens, latency_ms, error)
        )
        conn.commit()
        return cursor.lastrowid


@require_user_id
def get_model_stats(*, user_id: int) -> dict:
    """Kullanicinin model kullanim istatistiklerini getirir.
    
    Args:
        user_id: Kullanici ID (zorunlu keyword arg)
        
    Returns:
        Istatistik dict
    """
    with get_db() as conn:
        # Toplam cagri sayisi
        cursor = conn.execute(
            "SELECT COUNT(*) FROM model_calls WHERE user_id = ?",
            (user_id,)
        )
        total_calls = cursor.fetchone()[0]
        
        # Toplam token kullanimi
        cursor = conn.execute(
            """SELECT COALESCE(SUM(prompt_tokens), 0), 
                      COALESCE(SUM(completion_tokens), 0)
               FROM model_calls WHERE user_id = ?""",
            (user_id,)
        )
        tokens = cursor.fetchone()
        
        # Ortalama latency
        cursor = conn.execute(
            "SELECT AVG(latency_ms) FROM model_calls WHERE user_id = ? AND latency_ms IS NOT NULL",
            (user_id,)
        )
        avg_latency = cursor.fetchone()[0]
        
        # Model bazli dagilim
        cursor = conn.execute(
            """SELECT model_name, COUNT(*) as count
               FROM model_calls WHERE user_id = ?
               GROUP BY model_name ORDER BY count DESC""",
            (user_id,)
        )
        model_usage = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            'total_calls': total_calls,
            'prompt_tokens': tokens[0],
            'completion_tokens': tokens[1],
            'total_tokens': tokens[0] + tokens[1],
            'avg_latency_ms': round(avg_latency, 2) if avg_latency else 0,
            'model_usage': model_usage
        }
