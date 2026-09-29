import { DocumentItem, Citation, SystemHealth } from '../types';

const API_BASE = '/api/v1';

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchDocuments(workspaceId = 'default'): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/documents?workspace_id=${workspaceId}`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  return res.json();
}

export async function ingestUrl(url: string, workspaceId = 'default', title?: string): Promise<DocumentItem> {
  const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
  const endpoint = isYouTube ? `${API_BASE}/documents/youtube` : `${API_BASE}/documents/url`;

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, workspace_id: workspaceId, title })
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to ingest URL');
  }
  return data;
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete document');
}

export interface QueryResponse {
  question: string;
  standalone_query: string;
  answer: string;
  citations: Citation[];
  has_sufficient_context: boolean;
  retrieved_count: number;
  latency_seconds: number;
}

export async function queryRAG(
  question: string,
  history: { role: string; content: string }[] = [],
  workspaceId = 'default'
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/chat/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      history,
      workspace_id: workspaceId,
      top_k: 5,
      enable_query_rewriting: true,
      enable_reranking: true
    })
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'RAG query failed');
  }
  return data;
}
