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
  retryJob,
  subscribeToJobEvents
} from './services/api';

export const App: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [selectedScope, setSelectedScope] = useState<string[]>([]);
  const [activeJobs, setActiveJobs] = useState<IngestionJobItem[]>([]);
  const [darkMode, setDarkMode] = useState(true);

  // Active SSE connection cleanup functions keyed by job_id
  const eventSourcesRef = useRef<Map<string, () => void>>(new Map());

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

  // Clean up all active SSE streams on unmount to prevent orphaned connections
  useEffect(() => {
    return () => {
      eventSourcesRef.current.forEach((cleanup) => {
        try {
          cleanup();
        } catch (e) {
          console.warn('Error closing SSE stream on unmount', e);
        }
      });
      eventSourcesRef.current.clear();
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

  /**
   * Connects to the real-time Server-Sent Events stream for an ingestion job.
   * Completely replaces legacy 1-second HTTP polling.
   */
  const connectSSE = (job: IngestionJobItem) => {
    // If an existing subscription exists for this job, close it first
    if (eventSourcesRef.current.has(job.job_id)) {
      eventSourcesRef.current.get(job.job_id)!();
      eventSourcesRef.current.delete(job.job_id);
    }

    // Add or update job in the activeJobs list
    setActiveJobs((prev) => {
      const idx = prev.findIndex((j) => j.job_id === job.job_id);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = { ...updated[idx], ...job };
        return updated;
      }
      return [job, ...prev];
    });

    const cleanup = subscribeToJobEvents(job.job_id, job.workspace_id || 'default', {
      onUpdate: (updatedJob) => {
        setActiveJobs((prev) =>
          prev.map((j) => (j.job_id === updatedJob.job_id ? { ...j, ...updatedJob } : j))
        );
      },
      onComplete: (completedJob) => {
        setActiveJobs((prev) =>
          prev.map((j) => (j.job_id === completedJob.job_id ? { ...j, ...completedJob } : j))
        );
        loadDocuments();
        loadHealth();
        eventSourcesRef.current.delete(completedJob.job_id);

        // Auto-clear success message after 4 seconds
        setTimeout(() => {
          setActiveJobs((prev) => prev.filter((j) => j.job_id !== completedJob.job_id));
        }, 4000);
      },
      onError: (failedJob) => {
        setActiveJobs((prev) =>
          prev.map((j) => (j.job_id === failedJob.job_id ? { ...j, ...failedJob } : j))
        );
        loadDocuments();
        eventSourcesRef.current.delete(failedJob.job_id);
      }
    });

    eventSourcesRef.current.set(job.job_id, cleanup);
  };

  const handleIngestUrl = async (url: string) => {
    setIsIngesting(true);
    try {
      const job = await ingestUrl(url);
      connectSSE(job);
      await loadDocuments();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleUploadFile = async (file: File) => {
    setIsIngesting(true);
    try {
      const job = await uploadFile(file);
      connectSSE(job);
      await loadDocuments();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      const retried = await retryJob(jobId);
      connectSSE(retried);
      await loadDocuments();
    } catch (err: any) {
      console.error('Failed to retry job', err);
    }
  };

  const handleDismissJob = (jobId: string) => {
    if (eventSourcesRef.current.has(jobId)) {
      eventSourcesRef.current.get(jobId)!();
      eventSourcesRef.current.delete(jobId);
    }
    setActiveJobs((prev) => prev.filter((j) => j.job_id !== jobId));
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

          {/* Real-Time Active Job Cards via SSE */}
          {activeJobs.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.5rem' }}>
              {activeJobs.map((job) => (
                <ActiveJobCard
                  key={job.job_id}
                  job={job}
                  onRetry={handleRetryJob}
                  onDismiss={() => handleDismissJob(job.job_id)}
                />
              ))}
            </div>
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
