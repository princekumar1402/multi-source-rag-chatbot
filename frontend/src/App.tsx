import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { SourceInput } from './components/SourceInput';
import { DocumentList } from './components/DocumentList';
import { ChatView } from './components/ChatView';
import { ActiveJobCard } from './components/ActiveJobCard';
import { DocumentItem, ChatMessage, SystemHealth, IngestionJobItem } from './types';
import {
  fetchHealth,
  fetchDocuments,
  ingestUrl,
  uploadFile,
  deleteDocument,
  queryRAG,
  fetchJobStatus,
  retryJob
} from './services/api';

export const App: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [selectedScope, setSelectedScope] = useState<string[]>([]);
  const [activeJob, setActiveJob] = useState<IngestionJobItem | null>(null);
  const [darkMode, setDarkMode] = useState(true);

  const pollingIntervalRef = useRef<any>(null);

  useEffect(() => {
    loadHealth();
    loadDocuments();
  }, []);

  useEffect(() => {
    if (darkMode) {
      document.body.classList.remove('light-theme');
    } else {
      document.body.classList.add('light-theme');
    }
  }, [darkMode]);

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const loadHealth = async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (e) {
      console.error('Failed to load system health', e);
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error('Failed to load documents', e);
    }
  };

  const startPolling = (jobId: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const job = await fetchJobStatus(jobId);
        setActiveJob(job);

        if (job.status === 'completed') {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
          await loadDocuments();
          await loadHealth();
          // Auto-clear success message after 4 seconds
          setTimeout(() => {
            setActiveJob((current) => (current?.job_id === jobId ? null : current));
          }, 4000);
        } else if (job.status === 'failed') {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
          await loadDocuments();
        }
      } catch (err) {
        console.error('Job status polling error', err);
      }
    }, 1000);
  };

  const handleIngestUrl = async (url: string) => {
    setIsIngesting(true);
    try {
      const job = await ingestUrl(url);
      setActiveJob(job);
      await loadDocuments();
      startPolling(job.job_id);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleUploadFile = async (file: File) => {
    setIsIngesting(true);
    try {
      const job = await uploadFile(file);
      setActiveJob(job);
      await loadDocuments();
      startPolling(job.job_id);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      const retried = await retryJob(jobId);
      setActiveJob(retried);
      await loadDocuments();
      startPolling(retried.job_id);
    } catch (err: any) {
      console.error('Failed to retry job', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      setSelectedScope((prev) => prev.filter((dId) => dId !== id));
      await loadDocuments();
      await loadHealth();
    } catch (e) {
      console.error('Failed to delete document', e);
    }
  };

  const handleSendMessage = async (text: string) => {
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsChatLoading(true);

    try {
      const historyPayload = messages.map((m) => ({
        role: m.role,
        content: m.content
      }));

      const response = await queryRAG(text, historyPayload, 'default', selectedScope);

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        latency_seconds: response.latency_seconds,
        has_sufficient_context: response.has_sufficient_context
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to generate response.'}`
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        health={health}
        darkMode={darkMode}
        onToggleTheme={() => setDarkMode(!darkMode)}
        documentCount={documents.length}
      />

      <main style={{ flex: 1, padding: '0 1rem 1rem 1rem', display: 'flex', gap: '1.25rem', height: 'calc(100vh - 90px)' }}>
        {/* Left Column: Ingestion & Knowledge Sources */}
        <div style={{ width: '400px', display: 'flex', flexDirection: 'column' }}>
          <SourceInput onIngestUrl={handleIngestUrl} onUploadFile={handleUploadFile} isLoading={isIngesting} />

          {activeJob && (
            <ActiveJobCard
              job={activeJob}
              onRetry={handleRetryJob}
              onDismiss={() => setActiveJob(null)}
            />
          )}

          <div style={{ flex: 1, minHeight: 0 }}>
            <DocumentList
              documents={documents}
              onDelete={handleDelete}
              isLoading={isIngesting}
            />
          </div>
        </div>

        {/* Right Column: Grounded Chat Workspace */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <ChatView
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isChatLoading}
            hasDocuments={documents.length > 0}
            documents={documents}
            selectedScope={selectedScope}
            onScopeChange={setSelectedScope}
          />
        </div>
      </main>
    </div>
  );
};
