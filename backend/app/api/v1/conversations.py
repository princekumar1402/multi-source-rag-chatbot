from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from sqlalchemy.orm import Session

from backend.app.schemas.conversation import ConversationCreate, ConversationResponse, MessageResponse
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.db.session import get_db

router = APIRouter()

@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    workspace_id: str = Query("default", description="Workspace ID to filter conversations"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
) -> List[ConversationResponse]:
    """List conversations belonging to a specific workspace."""
    WorkspaceRepository.get_or_create(db, workspace_id=workspace_id)
    db.commit()
    convs = ConversationRepository.list_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=limit)
    return [ConversationResponse.model_validate(c) for c in convs]

@router.post("", response_model=ConversationResponse, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db)
) -> ConversationResponse:
    """Create a new conversation session within a workspace."""
    WorkspaceRepository.get_or_create(db, workspace_id=payload.workspace_id)
    conv = ConversationRepository.create(
        db=db,
        workspace_id=payload.workspace_id,
        title=payload.title or "New Conversation",
        conversation_id=payload.conversation_id
    )
    db.commit()
    return ConversationResponse.model_validate(conv)

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
) -> List[MessageResponse]:
    """Get all messages for a specific conversation in chronological order."""
    conv = ConversationRepository.get(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = MessageRepository.list_by_conversation(db, conversation_id=conversation_id, limit=limit)
    return [MessageResponse.model_validate(m) for m in messages]
