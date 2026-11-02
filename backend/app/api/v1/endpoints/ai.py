from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.database import get_db
from app.core.dependencies import get_tenant_context, TenantContext
from app.models.models import AssistantConversation, AssistantMessage
from app.schemas.schemas import AIChatRequest, AIChatResponse
from app.services.ai_service import AIHotelAssistantService
from app.core.rate_limit import ai_chat_rate_limiter, rate_limit_dependency

router = APIRouter()

@router.post("/chat", response_model=AIChatResponse)
async def chat_with_assistant(
    data: AIChatRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Primary conversational endpoint for the AI Operations Assistant.
    Enforces verified tenant context, role authorization, quota metering, and grounded tool calling.
    """
    if not data.message or not data.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    # Enforce rate limit scoped to authenticated hotel and user session
    rate_key = f"ai_chat:{ctx.hotel_id}:{ctx.user.id}"
    allowed, count, retry_after = await ai_chat_rate_limiter.is_allowed(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI chat rate limit exceeded. Maximum 30 requests per minute. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)}
        )

    result = await AIHotelAssistantService.process_user_query(
        db=db,
        ctx=ctx,
        message_text=data.message.strip(),
        conversation_id=data.conversation_id,
        confirm_action_id=data.confirm_action_id,
        action_name=data.action_name,
        action_parameters=data.action_parameters,
        cancel_action_id=data.cancel_action_id
    )
    return AIChatResponse(**result)

@router.get("/conversations")
async def list_conversations(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists conversations belonging to the authenticated user in this hotel."""
    res = await db.execute(
        select(AssistantConversation)
        .where(
            AssistantConversation.hotel_id == ctx.hotel_id,
            AssistantConversation.user_id == ctx.user.id
        )
        .order_by(AssistantConversation.created_at.desc())
        .limit(20)
    )
    convs = res.scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at
        } for c in convs
    ]

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves message history for a conversation.
    Strictly enforces hotel_id and user_id ownership to prevent unauthorized data access.
    """
    res_conv = await db.execute(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.hotel_id == ctx.hotel_id,
            AssistantConversation.user_id == ctx.user.id
        )
    )
    conv = res_conv.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied."
        )

    res = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at.asc())
        .limit(50)
    )
    messages = res.scalars().all()
    return [
        {
            "id": m.id,
            "sender": m.sender,
            "content": m.content,
            "tool_calls": m.tool_calls,
            "created_at": m.created_at
        } for m in messages
    ]

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Deletes a conversation and all its messages."""
    res_conv = await db.execute(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.hotel_id == ctx.hotel_id,
            AssistantConversation.user_id == ctx.user.id
        )
    )
    conv = res_conv.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied."
        )

    await db.delete(conv)
    await db.commit()
    return {"message": "Conversation deleted successfully"}
