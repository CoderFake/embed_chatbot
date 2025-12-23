"""Service for fetching visitor data from database."""
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import visitors, chat_sessions, chat_messages
from app.services.provider import provider_service


async def get_visitor_data(
    visitor_id: str,
    bot_id: str,
    session_id: str,
    db: AsyncSession
) -> dict:
    """
    Query database for visitor conversation, profile, and bot config.
    
    Args:
        visitor_id: UUID of the visitor
        bot_id: UUID of the bot
        session_id: UUID of the chat session
        db: Database session
        
    Returns:
        Dictionary with conversation_history, visitor_profile, and bot_config
    """

    conversation_history = []
    visitor_profile = {}
    
    messages_query = (
        select(
            chat_messages.c.query,
            chat_messages.c.response,
            chat_messages.c.created_at
        )
        .where(chat_messages.c.session_id == session_id)
        .order_by(chat_messages.c.created_at)
    )
    messages_result = await db.execute(messages_query)
    messages = messages_result.fetchall()
    
    for msg in messages:
        conversation_history.append({
            "role": "user",
            "content": msg.query,
            "timestamp": msg.created_at.isoformat()
        })
        conversation_history.append({
            "role": "assistant",
            "content": msg.response,
            "timestamp": msg.created_at.isoformat()
        })
    
    visitor_query = select(
        visitors.c.name,
        visitors.c.email,
        visitors.c.phone,
        visitors.c.address,
        visitors.c.lead_score,
        visitors.c.lead_assessment
    ).where(visitors.c.id == visitor_id)
    visitor_result = await db.execute(visitor_query)
    visitor_row = visitor_result.fetchone()
    
    if visitor_row:
        visitor_profile = {
            "name": visitor_row.name,
            "email": visitor_row.email,
            "phone": visitor_row.phone,
            "address": visitor_row.address,
            "current_lead_score": visitor_row.lead_score,
            "previous_assessment": visitor_row.lead_assessment or {}
        }
    
    session_query = select(
        chat_sessions.c.extra_data
    ).where(chat_sessions.c.id == session_id)
    session_result = await db.execute(session_query)
    session_row = session_result.fetchone()
    
    if session_row and session_row.extra_data:
        long_term_memory = session_row.extra_data.get("long_term_memory")
        if long_term_memory:
            visitor_profile["long_term_memory"] = long_term_memory
    
    bot_config = await provider_service.get_bot_config_with_key_selection(bot_id, db)
    
    if not bot_config:
        raise ValueError(f"Failed to load bot configuration for bot_id={bot_id}")
    
    return {
        "conversation_history": conversation_history,
        "visitor_profile": visitor_profile,
        "bot_config": bot_config
    }
