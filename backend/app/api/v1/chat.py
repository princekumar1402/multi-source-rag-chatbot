from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, ChatTurn
from backend.app.core.dependencies import get_rag_engine
from backend.app.services.rag.engine import RAGEngine
from backend.app.db.session import get_db
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.core.cache import cache_manager

router = APIRouter()

@router.post("/query", response_model=RAGQueryResponse)
def execute_rag_query(
    payload: RAGQueryRequest,
    rag_engine: RAGEngine = Depends(get_rag_engine),
    db: Session = Depends(get_db)
) -> RAGQueryResponse:
    """
    Execute grounded RAG query over workspace documents.
    If conversation_id is supplied, loads persistent chat history from PostgreSQL,
    executes query rewriting & RAG synthesis, and persists both user & assistant turns.
    Returns strictly grounded answer, citations with timestamps/pages, and performance latency.
    """
    try:
        # Ensure workspace exists
        WorkspaceRepository.get_or_create(db, workspace_id=payload.workspace_id)

        # Validate document retrieval scope: strictly ensure documents belong to workspace AND status == 'ready'
        ready_doc_ids = cache_manager.ready_docs_cache.get(payload.workspace_id)
        if ready_doc_ids is None:
            ready_doc_ids = set(DocumentRepository.list_ready_ids_by_workspace(db, workspace_id=payload.workspace_id))
            cache_manager.ready_docs_cache.set(payload.workspace_id, ready_doc_ids, ttl_seconds=60)

        if payload.document_ids is not None:
            scoped_ids = [did for did in payload.document_ids if did in ready_doc_ids]
            if not scoped_ids:
                scoped_ids = ["__scoped_non_existent__"]
            payload.document_ids = scoped_ids
        else:
            # Default: restrict retrieval to all READY documents in this workspace
            payload.document_ids = list(ready_doc_ids) if ready_doc_ids else ["__no_ready_docs__"]

        conv = None
        if payload.conversation_id:

            # Retrieve or create conversation
            conv = ConversationRepository.get_by_id_and_workspace(
                db,
                conversation_id=payload.conversation_id,
                workspace_id=payload.workspace_id
            )
            if not conv:
                conv = ConversationRepository.create(
                    db,
                    workspace_id=payload.workspace_id,
                    title=payload.question[:60],
                    conversation_id=payload.conversation_id
                )

            # Load persistent message history from DB
            db_messages = MessageRepository.list_by_conversation(db, conv.id, limit=20)
            if db_messages:
                payload.history = [
                    ChatTurn(role=m.role, content=m.content)
                    for m in db_messages
                    if m.role in ("user", "assistant")
                ]

        # Execute pure RAG engine (free of any ORM dependencies)
        response = rag_engine.query(payload)

        # If conversation_id is active, persist turns to PostgreSQL
        if conv:
            MessageRepository.create(
                db=db,
                conversation_id=conv.id,
                role="user",
                content=payload.question
            )
            msg_meta = {
                "citations": [c.model_dump() for c in response.citations],
                "latency": response.latency,
                "retrieval": response.retrieval,
                "has_sufficient_context": response.has_sufficient_context
            }
            MessageRepository.create(
                db=db,
                conversation_id=conv.id,
                role="assistant",
                content=response.answer,
                msg_metadata=msg_meta
            )
            db.commit()
            response.conversation_id = conv.id

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG execution failed: {str(e)}")
