import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.workspace import Workspace
from backend.app.models.document import Document
from backend.app.models.chunk import Chunk
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.ingestion_job import IngestionJob
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.chunk_repo import ChunkRepository
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository

from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.rag.bm25 import BM25Retriever
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.engine import RAGEngine
from backend.app.schemas.rag import RAGQueryRequest

client = TestClient(app)

class MockLLM:
    """Deterministic Mock LLM for Phase 4 integration testing."""
    def __init__(self, answer_prefix: str = "Grounded response: "):
        self.answer_prefix = answer_prefix

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        if "quantum" in prompt.lower():
            return f"{self.answer_prefix}Quantum computing uses superposition of qubits according to [Source 1]."
        elif "photosynthesis" in prompt.lower():
            return f"{self.answer_prefix}Photosynthesis converts light energy into chemical energy according to [Source 1]."
        elif "follow-up" in prompt.lower() or "they" in prompt.lower() or "qubits" in prompt.lower():
            return f"{self.answer_prefix}Qubits exist in linear combinations of states according to [Source 1]."
        return "The available knowledge base sources do not contain enough information to answer this question."

# ==============================================================================
# 1. DATABASE ENTITIES & REPOSITORY TESTS
# ==============================================================================

def test_workspace_repository():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Research Lab", description="Quantum studies")
        db.commit()
        assert ws.id is not None
        assert ws.name == "Research Lab"

        fetched = WorkspaceRepository.get(db, ws.id)
        assert fetched is not None
        assert fetched.name == "Research Lab"

        workspaces = WorkspaceRepository.list(db)
        assert any(w.id == ws.id for w in workspaces)

def test_document_and_chunk_repositories():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Doc WS")
        db.commit()

        doc = DocumentRepository.create(
            db=db,
            workspace_id=ws.id,
            source_type="pdf",
            title="Quantum Foundations",
            content_hash="hash_quantum_123",
            file_name="quantum.pdf",
            status="pending",
            size_bytes=1024,
            doc_metadata={"author": "Einstein"}
        )
        db.commit()
        assert doc.id is not None
        assert doc.status == "pending"

        # Update status
        updated = DocumentRepository.update_status(db, doc.id, status="ready", chunk_count=2)
        db.commit()
        assert updated.status == "ready"
        assert updated.chunk_count == 2

        # Create chunks
        chunks_data = [
            {
                "id": f"{doc.id}_0",
                "document_id": doc.id,
                "workspace_id": ws.id,
                "chunk_index": 0,
                "text": "Quantum superposition is fundamental.",
                "content_hash": "chash_0",
                "source_type": "pdf",
                "source_name": "Quantum Foundations",
                "page_number": 1,
                "token_count": 5
            },
            {
                "id": f"{doc.id}_1",
                "document_id": doc.id,
                "workspace_id": ws.id,
                "chunk_index": 1,
                "text": "Entanglement links two particles.",
                "content_hash": "chash_1",
                "source_type": "pdf",
                "source_name": "Quantum Foundations",
                "page_number": 2,
                "token_count": 4
            }
        ]
        chunks = ChunkRepository.create_many(db, chunks_data)
        db.commit()
        assert len(chunks) == 2

        doc_chunks = ChunkRepository.list_by_document(db, doc.id)
        assert len(doc_chunks) == 2
        assert doc_chunks[0].page_number == 1
        assert doc_chunks[1].page_number == 2

def test_conversation_and_message_repositories():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Chat WS")
        db.commit()

        conv = ConversationRepository.create(db, workspace_id=ws.id, title="Quantum Chat")
        db.commit()
        assert conv.id is not None
        assert conv.title == "Quantum Chat"

        msg1 = MessageRepository.create(db, conversation_id=conv.id, role="user", content="What is a qubit?")
        msg2 = MessageRepository.create(
            db,
            conversation_id=conv.id,
            role="assistant",
            content="A qubit is a two-state quantum mechanical system.",
            msg_metadata={"latency": {"total_ms": 120.0}}
        )
        db.commit()

        history = MessageRepository.list_by_conversation(db, conv.id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        assert history[1].msg_metadata["latency"]["total_ms"] == 120.0

def test_ingestion_job_repository():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Job WS")
        db.commit()

        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws.id,
            source_type="pdf",
            status="pending"
        )
        db.commit()
        assert job.id is not None
        assert job.status == "pending"

        IngestionJobRepository.update_status(db, job.id, status="processing")
        db.commit()
        fetched = IngestionJobRepository.get(db, job.id)
        assert fetched.status == "processing"
        assert fetched.started_at is not None

        IngestionJobRepository.update_status(db, job.id, status="completed")
        db.commit()
        assert fetched.completed_at is not None

# ==============================================================================
# 2. CONSTRAINTS & CASCADING DELETION TESTS
# ==============================================================================

def test_duplicate_document_hash_constraint():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Hash WS")
        db.commit()

        DocumentRepository.create(
            db, workspace_id=ws.id, source_type="txt", title="Doc1", content_hash="same_hash_123"
        )
        db.commit()

        # Second insert with identical workspace_id and content_hash must violate unique constraint
        with pytest.raises(IntegrityError):
            DocumentRepository.create(
                db, workspace_id=ws.id, source_type="txt", title="Doc2", content_hash="same_hash_123"
            )
            db.commit()
        db.rollback()

def test_duplicate_chunk_index_constraint():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Chunk Index WS")
        db.commit()
        doc = DocumentRepository.create(
            db, workspace_id=ws.id, source_type="txt", title="Doc", content_hash="h1"
        )
        db.commit()

        ChunkRepository.create_many(db, [
            {"id": "c1", "document_id": doc.id, "workspace_id": ws.id, "chunk_index": 0, "text": "A", "source_type": "txt", "source_name": "Doc"},
        ])
        db.commit()

        with pytest.raises(IntegrityError):
            ChunkRepository.create_many(db, [
                {"id": "c2", "document_id": doc.id, "workspace_id": ws.id, "chunk_index": 0, "text": "B", "source_type": "txt", "source_name": "Doc"},
            ])
            db.commit()
        db.rollback()

def test_cascading_deletion():
    with SessionLocal() as db:
        ws = WorkspaceRepository.create(db, name="Cascade WS")
        db.commit()
        doc = DocumentRepository.create(
            db, workspace_id=ws.id, source_type="txt", title="Doc Cascade", content_hash="ch1"
        )
        db.commit()
        ChunkRepository.create_many(db, [
            {"id": "c_casc", "document_id": doc.id, "workspace_id": ws.id, "chunk_index": 0, "text": "T", "source_type": "txt", "source_name": "Doc"}
        ])
        conv = ConversationRepository.create(db, workspace_id=ws.id, title="Chat Cascade")
        db.commit()
        MessageRepository.create(db, conversation_id=conv.id, role="user", content="Hi")
        db.commit()

        # Deleting workspace must cascade to all child records
        WorkspaceRepository.delete(db, ws.id)
        db.commit()

    with SessionLocal() as verify_db:
        assert DocumentRepository.get(verify_db, doc.id) is None
        assert ChunkRepository.get(verify_db, "c_casc") is None
        assert ConversationRepository.get(verify_db, conv.id) is None


# ==============================================================================
# 3. FULL INGESTION, RETRIEVAL & CITATION CHAIN
# ==============================================================================

def test_full_ingestion_and_rag_chain(tmp_path):
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    bm25 = BM25Retriever()
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store, keyword_retriever=bm25)

    content = b"Quantum computing utilizes qubits. Unlike classical bits, qubits can exist in a superposition of both zero and one states simultaneously."
    doc = pipeline.process_file(content, "quantum_intro.txt", workspace_id="ws_rag_chain")

    assert doc.status.value == "ready"
    assert doc.chunk_count > 0

    # Verify PostgreSQL records
    with SessionLocal() as db:
        db_doc = DocumentRepository.get(db, doc.id)
        assert db_doc is not None
        assert db_doc.status == "ready"

        db_chunks = ChunkRepository.list_by_document(db, doc.id)
        assert len(db_chunks) == doc.chunk_count
        assert "superposition" in db_chunks[0].text

    # Assemble RAG Engine
    dense_retriever = DenseRetrieverWithReranker(embedder=embedder, vector_store=store)
    hybrid = HybridRetriever(dense_retriever=dense_retriever, keyword_retriever=bm25)
    selector = ContextSelector(min_relevance_score=0.01)
    llm = MockLLM()
    rag_engine = RAGEngine(retriever=hybrid, llm=llm, context_selector=selector)

    # Execute query
    request = RAGQueryRequest(
        question="What can qubits do in quantum computing?",
        workspace_id="ws_rag_chain"
    )
    response = rag_engine.query(request)

    assert response.has_sufficient_context is True
    assert "superposition" in response.answer
    assert len(response.citations) > 0
    # Verify citation fields originate from PostgreSQL chunk metadata
    cit = response.citations[0]
    assert cit.document_id == doc.id
    assert cit.chunk_id == db_chunks[0].id
    assert cit.source_title == "quantum_intro"

# ==============================================================================
# 4. DELETION LIFECYCLE (DB, FAISS & BM25 PURGE)
# ==============================================================================

def test_document_deletion_lifecycle(tmp_path):
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    bm25 = BM25Retriever()
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store, keyword_retriever=bm25)

    content = b"Photosynthesis is used by green plants to synthesize nutrients from carbon dioxide and water."
    doc = pipeline.process_file(content, "bio.txt", workspace_id="ws_delete")

    assert store.count("ws_delete") > 0
    assert len(bm25.chunks) > 0

    # Delete document
    deleted = pipeline.delete_document(doc.id)
    assert deleted is True

    # 1. FAISS count is zero
    assert store.count("ws_delete") == 0

    # 2. BM25 chunks for this doc are gone
    assert not any(c.metadata.document_id == doc.id for c in bm25.chunks)

    # 3. PostgreSQL records are gone
    with SessionLocal() as db:
        assert DocumentRepository.get(db, doc.id) is None
        assert len(ChunkRepository.list_by_document(db, doc.id)) == 0

# ==============================================================================
# 5. PERSISTENT CHAT HISTORY & CONVERSATION API
# ==============================================================================

def test_persistent_chat_conversation_flow(tmp_path):
    conv_id = f"test_conv_{uuid.uuid4().hex[:8]}"

    # Send first turn via Chat API
    payload1 = {
        "question": "What is quantum computing?",
        "workspace_id": "ws_chat_flow",
        "conversation_id": conv_id,
        "history": []
    }
    resp1 = client.post("/api/v1/chat/query", json=payload1)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["conversation_id"] == conv_id

    # Verify messages persisted in PostgreSQL
    with SessionLocal() as db:
        messages = MessageRepository.list_by_conversation(db, conv_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "What is quantum computing?"
        assert messages[1].role == "assistant"

    # Send second turn without passing history in payload (should load from DB)
    payload2 = {
        "question": "How do they utilize qubits?",
        "workspace_id": "ws_chat_flow",
        "conversation_id": conv_id,
        "history": []
    }
    resp2 = client.post("/api/v1/chat/query", json=payload2)
    assert resp2.status_code == 200

    # Verify API lists conversation messages
    resp_msgs = client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert resp_msgs.status_code == 200
    all_msgs = resp_msgs.json()
    assert len(all_msgs) == 4
    assert all_msgs[0]["content"] == "What is quantum computing?"
    assert all_msgs[2]["content"] == "How do they utilize qubits?"

# ==============================================================================
# 6. WORKSPACE ISOLATION VERIFICATION
# ==============================================================================

def test_strict_workspace_isolation(tmp_path):
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    bm25 = BM25Retriever()
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store, keyword_retriever=bm25)

    # Workspace A: Quantum Document
    doc_a = pipeline.process_file(
        b"Quantum computing works with superposition of qubits in state |psi> = alpha|0> + beta|1>.",
        "quantum.txt",
        workspace_id="ws_A"
    )

    # Workspace B: Biology Document
    doc_b = pipeline.process_file(
        b"Photosynthesis occurs in chloroplasts containing chlorophyll pigments that absorb light.",
        "photosynthesis.txt",
        workspace_id="ws_B"
    )

    dense = DenseRetrieverWithReranker(embedder=embedder, vector_store=store)
    hybrid = HybridRetriever(dense_retriever=dense, keyword_retriever=bm25)
    selector = ContextSelector(min_relevance_score=0.01)
    llm = MockLLM()
    rag_engine = RAGEngine(retriever=hybrid, llm=llm, context_selector=selector)

    # Query Workspace A with a Workspace B topic
    req_a_for_b = RAGQueryRequest(question="Where does photosynthesis occur?", workspace_id="ws_A")
    resp_a_for_b = rag_engine.query(req_a_for_b)
    # Must NOT retrieve anything from Workspace B
    assert resp_a_for_b.has_sufficient_context is False
    assert len(resp_a_for_b.citations) == 0

    # Query Workspace B with a Workspace A topic
    req_b_for_a = RAGQueryRequest(question="What is quantum superposition?", workspace_id="ws_B")
    resp_b_for_a = rag_engine.query(req_b_for_a)
    # Must NOT retrieve anything from Workspace A
    assert resp_b_for_a.has_sufficient_context is False
    assert len(resp_b_for_a.citations) == 0

    # Query Workspace A with its own topic
    req_a_valid = RAGQueryRequest(question="What is quantum superposition?", workspace_id="ws_A")
    resp_a_valid = rag_engine.query(req_a_valid)
    assert resp_a_valid.has_sufficient_context is True
    assert all(c.document_id == doc_a.id for c in resp_a_valid.citations)

# ==============================================================================
# 7. NEW WORKSPACE & CONVERSATION REST APIS
# ==============================================================================

def test_workspace_and_conversation_apis():
    # 1. Create Workspace
    resp = client.post("/api/v1/workspaces", json={"name": "Engineering Team", "description": "Backend RAG"})
    assert resp.status_code == 201
    ws_data = resp.json()
    ws_id = ws_data["id"]
    assert ws_data["name"] == "Engineering Team"

    # 2. Get Workspace
    resp_get = client.get(f"/api/v1/workspaces/{ws_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == ws_id

    # 3. List Workspaces
    resp_list = client.get("/api/v1/workspaces")
    assert resp_list.status_code == 200
    assert any(w["id"] == ws_id for w in resp_list.json())

    # 4. Create Conversation
    resp_conv = client.post("/api/v1/conversations", json={"workspace_id": ws_id, "title": "Onboarding"})
    assert resp_conv.status_code == 201
    conv_id = resp_conv.json()["id"]

    # 5. List Conversations
    resp_convs = client.get(f"/api/v1/conversations?workspace_id={ws_id}")
    assert resp_convs.status_code == 200
    assert any(c["id"] == conv_id for c in resp_convs.json())
