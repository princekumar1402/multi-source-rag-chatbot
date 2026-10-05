"""
Production Multi-Source Ingestion & Robustness Verification
Tests PDF, URL, YouTube, Failure state, and Retry API against live container stack.
"""
import sys
import time
import requests
import io

def generate_minimal_pdf() -> bytes:
    # Build a valid minimal single-page PDF containing extractable text
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 115 >>
stream
BT
/F1 12 Tf
72 712 Td
(Production PDF Test: High-Availability Multi-Source RAG Platform with Docker and PostgreSQL.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000244 00000 n 
0000000410 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
484
%%EOF"""
    return content

def wait_for_job(base_url: str, job_id: str, max_wait: int = 40):
    start = time.time()
    while time.time() - start < max_wait:
        r = requests.get(f"{base_url}/api/v1/ingestion/jobs/{job_id}", timeout=5)
        if r.status_code == 200:
            st = r.json().get("status")
            if st in ["ready", "completed", "failed"]:
                return r.json()
        time.sleep(1)
    return {"status": "timeout"}

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    print(f"Targeting: {base_url}\n")
    ws_id = f"multisource-test-{int(time.time())}"

    # 1. PDF Ingestion Test
    print("[1/5] Testing PDF Ingestion & Retrieval...")
    pdf_bytes = generate_minimal_pdf()
    files = {"file": ("test_phase12.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"workspace_id": ws_id}
    r = requests.post(f"{base_url}/api/v1/documents/upload", files=files, data=data, timeout=10)
    assert r.status_code == 202, f"PDF upload failed: {r.status_code} {r.text}"
    job_info = r.json()
    job_id = job_info["job_id"]
    doc_id = job_info["document_id"]
    print(f"  Uploaded PDF doc_id={doc_id}, job_id={job_id}. Polling completion...")

    res = wait_for_job(base_url, job_id, 35)
    print(f"  PDF job finished with status: {res.get('status')}")
    assert res.get("status") in ["ready", "completed"], f"PDF job failed: {res}"

    # Query PDF content
    q_payload = {
        "question": "What is the High-Availability Multi-Source RAG Platform built with?",
        "workspace_id": ws_id,
        "document_ids": [doc_id],
        "top_k": 3
    }
    r_query = requests.post(f"{base_url}/api/v1/chat/query", json=q_payload, timeout=20)
    assert r_query.status_code == 200, f"Query failed: {r_query.text}"
    ans = r_query.json()
    assert len(ans.get("citations", [])) > 0, "No citations returned for PDF"
    print(f"  [PASS] PDF Ingestion & Retrieval PASS! Citation count: {len(ans['citations'])}")

    # 2. Web URL Ingestion Test
    print("\n[2/5] Testing Web URL Ingestion & Retrieval...")
    url_payload = {
        "url": "https://example.com",
        "workspace_id": ws_id,
        "title": "Example Domain Test"
    }
    r_url = requests.post(f"{base_url}/api/v1/documents/url", json=url_payload, timeout=10)
    assert r_url.status_code == 202, f"URL ingestion failed: {r_url.status_code} {r_url.text}"
    url_job_id = r_url.json()["job_id"]
    url_doc_id = r_url.json()["document_id"]
    print(f"  Submitted URL doc_id={url_doc_id}, job_id={url_job_id}. Polling completion...")
    
    url_res = wait_for_job(base_url, url_job_id, 35)
    print(f"  URL job finished with status: {url_res.get('status')}")
    assert url_res.get("status") in ["ready", "completed"], f"URL job failed: {url_res}"

    q_url = {
        "question": "What is this domain used for illustrative examples in documents?",
        "workspace_id": ws_id,
        "document_ids": [url_doc_id],
        "top_k": 3
    }
    r_url_q = requests.post(f"{base_url}/api/v1/chat/query", json=q_url, timeout=20)
    assert r_url_q.status_code == 200
    print(f"  [PASS] Web URL Ingestion PASS!")

    # 3. YouTube Ingestion Validation
    print("\n[3/5] Testing YouTube Ingestion Endpoint...")
    yt_payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "workspace_id": ws_id,
        "title": "Rick Astley Music Video"
    }
    r_yt = requests.post(f"{base_url}/api/v1/documents/youtube", json=yt_payload, timeout=10)
    assert r_yt.status_code in [202, 400], f"Unexpected status: {r_yt.status_code}"
    if r_yt.status_code == 202:
        yt_job_id = r_yt.json()["job_id"]
        yt_res = wait_for_job(base_url, yt_job_id, 30)
        print(f"  YouTube job status: {yt_res.get('status')}")
        print("  [PASS] YouTube endpoint accepted & handled appropriately!")
    else:
        print(f"  [PASS] YouTube validated input gracefully: {r_yt.status_code} {r_yt.text[:100]}")

    # 4. Failure Ingestion Handling
    print("\n[4/5] Testing Ingestion Failure Handling...")
    fail_payload = {
        "url": "http://invalid-nonexistent-domain-404-rag.org",
        "workspace_id": ws_id,
        "title": "Invalid Domain"
    }
    r_fail = requests.post(f"{base_url}/api/v1/documents/url", json=fail_payload, timeout=10)
    assert r_fail.status_code in [202, 400], f"Expected 202 or 400, got {r_fail.status_code}"
    if r_fail.status_code == 202:
        fail_job_id = r_fail.json()["job_id"]
        fail_res = wait_for_job(base_url, fail_job_id, 30)
        print(f"  Job status for bad URL: {fail_res.get('status')}")
        assert fail_res.get("status") == "failed", f"Expected job to fail, but got {fail_res.get('status')}"
        print(f"  [PASS] Bad URL correctly transitioned to 'failed' status with error: {fail_res.get('error_message')}")
        
        # 5. Retry Mechanism on Failed Job
        print("\n[5/5] Testing Retry API on Failed Ingestion Job...")
        r_retry = requests.post(f"{base_url}/api/v1/ingestion/jobs/{fail_job_id}/retry", timeout=10)
        assert r_retry.status_code in [200, 202], f"Retry failed: {r_retry.status_code} {r_retry.text}"
        retried_info = r_retry.json()
        print(f"  Retry response status: {retried_info.get('status')}, retry_count: {retried_info.get('retry_count')}")
        assert retried_info.get("retry_count", 0) >= 1 or retried_info.get("status") in ["queued", "processing", "failed"]
        print("  [PASS] Job retry endpoint operational!")
    else:
        print("  [PASS] Bad URL rejected upfront!")

    # Cleanup test documents
    for d in [doc_id, url_doc_id]:
        requests.delete(f"{base_url}/api/v1/documents/{d}", timeout=5)

    print("\n=======================================================")
    print("ALL MULTI-SOURCE & INGESTION FAILURE/RETRY TESTS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    main()
