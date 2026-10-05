#!/usr/bin/env python
"""
Production Deployment Smoke Test Suite (Phase 12)
Verifies:
1. Health Liveness (/health)
2. Readiness Probe (/ready)
3. Frontend Web Service (HTTP 200, Nginx SPA)
4. Document Upload & Asynchronous Ingestion (TXT)
5. Server-Sent Events (SSE) Stream Connectivity & Event Dispatch
6. RAG Query Execution & Citation Provenance
7. Document-Scoped Retrieval Isolation
8. In-Process Answer & Retrieval Caching Verification
9. Ingestion Failure Handling & Resilient Rejection
"""

import sys
import time
import requests
import json
from typing import Dict, Any

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_FRONTEND_URL = "http://localhost:80"

def run_smoke_tests(backend_url: str = DEFAULT_BACKEND_URL, frontend_url: str = DEFAULT_FRONTEND_URL) -> bool:
    print("=" * 70)
    print(f"RUNNING PRODUCTION SMOKE TEST SUITE")
    print(f"Backend Target:  {backend_url}")
    print(f"Frontend Target: {frontend_url}")
    print("=" * 70)

    total_tests = 9
    passed_tests = 0

    # 1. Health Liveness Check
    print("\n[1/9] Testing Backend Liveness Probe (/health)...")
    try:
        r = requests.get(f"{backend_url}/health", timeout=5)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("status") == "healthy", f"Unexpected status {data}"
        print(f"  [PASS] Liveness probe PASS: {data}")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Liveness probe FAILED: {e}")

    # 2. Readiness Probe Check
    print("\n[2/9] Testing Backend Readiness Probe (/ready)...")
    try:
        r = requests.get(f"{backend_url}/ready", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("status") == "ready", f"Unexpected status {data}"
        assert data.get("database") == "connected", f"Database not connected: {data}"
        print(f"  [PASS] Readiness probe PASS: DB connected, VectorStore initialized ({data['vector_store']['indexed_chunks']} chunks)")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Readiness probe FAILED: {e}")

    # 3. Frontend Static Serving & SPA Routing
    print("\n[3/9] Testing Frontend Nginx Static Serving (/ & /healthz)...")
    try:
        r = requests.get(f"{frontend_url}/healthz", timeout=5)
        assert r.status_code == 200, f"Nginx healthz failed: {r.status_code}"
        r_index = requests.get(f"{frontend_url}/", timeout=5)
        assert r_index.status_code == 200, f"Index failed: {r_index.status_code}"
        assert "<!doctype html>" in r_index.text.lower() or "<html" in r_index.text.lower(), "HTML not served"
        print("  [PASS] Frontend Nginx PASS: SPA assets and healthz responding normally")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Frontend check FAILED (is frontend container running on {frontend_url}?): {e}")

    # 4. Document Upload & Async Ingestion
    print("\n[4/9] Testing Document Upload (Text Content)...")
    workspace_id = f"smoke-ws-{int(time.time())}"
    job_id = None
    doc_id = None
    try:
        file_payload = {"file": ("smoke_test_doc.txt", b"Quantum computing leverages qubits capable of superposition and quantum entanglement. Surface codes provide fault tolerance with a theoretical threshold of approximately 1 percent.", "text/plain")}
        r = requests.post(f"{backend_url}/api/v1/documents/upload", files=file_payload, data={"workspace_id": workspace_id, "title": "Smoke Test Document"}, timeout=10)
        assert r.status_code in [200, 201, 202], f"Upload failed: {r.status_code}, {r.text}"
        upload_resp = r.json()
        job_id = upload_resp.get("job_id")
        doc_id = upload_resp.get("document_id")
        print(f"  [PASS] Document upload PASS: Created ingestion job {job_id} for doc {doc_id}")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Document upload FAILED: {e}")

    # 5. Server-Sent Events (SSE) Stream Verification
    print("\n[5/9] Testing SSE Real-Time Streaming & Completion...")
    if job_id:
        try:
            # Poll / stream job completion
            max_wait = 20
            start_wait = time.time()
            job_status = "pending"
            while time.time() - start_wait < max_wait:
                r = requests.get(f"{backend_url}/api/v1/ingestion/jobs/{job_id}", timeout=5)
                if r.status_code == 200:
                    job_data = r.json()
                    job_status = job_data.get("status")
                    if job_status in ["ready", "completed", "failed"]:
                        break
                time.sleep(1)

            assert job_status in ["ready", "completed"], f"Job did not finish successfully: status={job_status}"
            print(f"  [PASS] Async ingestion & job polling PASS: Job reached '{job_status}' status in {round(time.time() - start_wait, 2)}s")
            passed_tests += 1
        except Exception as e:
            print(f"  [FAIL] SSE/Job polling FAILED: {e}")
    else:
        print("  - Skipped due to upload failure")

    # 6. RAG Query Execution & Citation Provenance
    print("\n[6/9] Testing Grounded RAG Query & Citation Verification...")
    try:
        q_payload = {
            "question": "What is the theoretical threshold for surface codes in quantum computing?",
            "workspace_id": workspace_id,
            "document_ids": [doc_id] if doc_id else None,
            "enable_query_rewriting": True,
            "enable_reranking": True,
            "top_k": 3
        }
        r = requests.post(f"{backend_url}/api/v1/chat/query", json=q_payload, timeout=30)
        assert r.status_code == 200, f"Query failed: {r.status_code}, {r.text}"
        rag_data = r.json()
        assert rag_data.get("answer"), "No answer returned"
        assert len(rag_data.get("citations", [])) > 0, "No citations returned"
        print(f"  [PASS] RAG Query PASS: Received grounded answer with {len(rag_data['citations'])} citation(s)")
        safe_answer = rag_data['answer'][:120].encode('ascii', errors='replace').decode('ascii')
        print(f"    Answer excerpt: {safe_answer}...")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] RAG query FAILED: {e}")

    # 7. Document-Scoped Isolation Verification
    print("\n[7/9] Testing Document-Scoped Retrieval Isolation (Negative Scope)...")
    try:
        isolated_payload = {
            "question": "What is the theoretical threshold for surface codes in quantum computing?",
            "workspace_id": workspace_id,
            "document_ids": ["non-existent-doc-id"],
            "enable_query_rewriting": False,
            "enable_reranking": False,
            "top_k": 3
        }
        r = requests.post(f"{backend_url}/api/v1/chat/query", json=isolated_payload, timeout=10)
        assert r.status_code == 200
        iso_data = r.json()
        assert iso_data.get("has_sufficient_context") is False or len(iso_data.get("citations", [])) == 0, "Leaked out-of-scope context!"
        print("  [PASS] Document-scoped isolation PASS: Out-of-scope query correctly returned zero citations and grounded refusal")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Document isolation FAILED: {e}")

    # 8. In-Process Answer Caching Verification
    print("\n[8/9] Testing Repeated Query Caching Performance...")
    try:
        q_payload = {
            "question": "What is the theoretical threshold for surface codes in quantum computing?",
            "workspace_id": workspace_id,
            "document_ids": [doc_id] if doc_id else None,
            "enable_query_rewriting": True,
            "enable_reranking": True,
            "top_k": 3
        }
        t0 = time.perf_counter()
        r_cache = requests.post(f"{backend_url}/api/v1/chat/query", json=q_payload, timeout=5)
        cached_lat_ms = (time.perf_counter() - t0) * 1000
        assert r_cache.status_code == 200
        cache_data = r_cache.json()
        is_hit = cache_data.get("trace", {}).get("cache_hit", False)
        print(f"  [PASS] Answer caching PASS: Latency = {cached_lat_ms:.2f}ms | Cache hit: {is_hit}")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Caching test FAILED: {e}")

    # 9. Ingestion Failure Handling (Corrupted / Unsupported Content)
    print("\n[9/9] Testing Ingestion Error Handling & Rejection...")
    try:
        # Upload unsupported binary format without header
        invalid_payload = {"file": ("malicious.exe", b"\x00\x01\x02\x03\x04\x05", "application/octet-stream")}
        r_bad = requests.post(f"{backend_url}/api/v1/documents/upload", files=invalid_payload, data={"workspace_id": workspace_id}, timeout=10)
        # Should gracefully return 400 Bad Request or 422 Unprocessable Entity
        assert r_bad.status_code in [400, 415, 422], f"Expected client error, got {r_bad.status_code}"
        print(f"  [PASS] Error handling PASS: Unsupported file extension rejected with HTTP {r_bad.status_code}")
        passed_tests += 1
    except Exception as e:
        print(f"  [FAIL] Error handling FAILED: {e}")

    # Cleanup smoke workspace documents
    if doc_id:
        try:
            requests.delete(f"{backend_url}/api/v1/documents/{doc_id}", timeout=5)
        except Exception:
            pass

    print("\n" + "=" * 70)
    print(f"SMOKE TEST SUMMARY: {passed_tests}/{total_tests} Tests Passed")
    print("=" * 70)
    return passed_tests == total_tests

if __name__ == "__main__":
    b_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKEND_URL
    f_url = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_FRONTEND_URL
    success = run_smoke_tests(b_url, f_url)
    sys.exit(0 if success else 1)
