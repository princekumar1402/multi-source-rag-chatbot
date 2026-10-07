import React, { useState, useEffect, useRef } from 'react';
import { Sidebar, ActiveNavTab } from './components/Sidebar';
import { ChatHeader } from './components/ChatHeader';
import { ChatWorkspace } from './components/ChatWorkspace';
import { KnowledgeIntelligencePanel } from './components/KnowledgeIntelligencePanel';
import { DocumentsView } from './components/DocumentsView';
import { IngestionView } from './components/IngestionView';
import { SourcesView } from './components/SourcesView';
import { UploadModal } from './components/UploadModal';
import { CommandMenuModal } from './components/CommandMenuModal';
import { SettingsModal } from './components/SettingsModal';
import {
  DocumentItem,
  ChatMessage,
  SystemHealth,
  IngestionJobItem,
  Citation,
  ConversationItem
} from './types';
import {
  fetchHealth,
  fetchDocuments,
  ingestUrl,
  uploadFile,
  deleteDocument,
  queryRAG,
  retryJob,
  subscribeToJobEvents,
  fetchConversations,
  createConversation,
  fetchConversationMessages
} from './services/api';

export const App: React.FC = () => {
  // Navigation & Modals
  const [activeTab, setActiveTab] = useState<ActiveNavTab>('chat');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false); // Primary is light mode
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showIntelligencePanel, setShowIntelligencePanel] = useState(true);

  // Data & State
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [selectedScope, setSelectedScope] = useState<string[]>([]);
  const [activeJobs, setActiveJobs] = useState<IngestionJobItem[]>([]);

  // Loading States
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);

  // Latest Retrieval Telemetry
  const [latestRetrieval, setLatestRetrieval] = useState<any>(null);
  const [latestLatency, setLatestLatency] = useState<any>(null);

  // Active SSE connection cleanup functions keyed by job_id
  const eventSourcesRef = useRef<Map<string, () => void>>(new Map());

  // Initial Data Load
  useEffect(() => {
    loadHealth();
    loadDocuments();
    loadConversations();
  }, []);

  // Theme Sync
  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
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

  const loadConversations = async () => {
    try {
      const convList = await fetchConversations();
      setConversations(convList);
      if (convList.length > 0 && !activeConversationId) {
        const firstConv = convList[0];
        setActiveConversationId(firstConv.id);
        loadConversationMessages(firstConv.id);
      }
    } catch (e) {
      console.error('Failed to load conversations', e);
    }
  };

  const loadConversationMessages = async (convId: string) => {
    try {
      const dbMsgs = await fetchConversationMessages(convId);
      const parsedMsgs: ChatMessage[] = dbMsgs.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.msg_metadata?.citations || [],
        latency_seconds: m.msg_metadata?.latency?.total_ms ? m.msg_metadata.latency.total_ms / 1000 : undefined,
        has_sufficient_context: m.msg_metadata?.has_sufficient_context ?? true,
        retrieval: m.msg_metadata?.retrieval,
        latency: m.msg_metadata?.latency
      }));
      setMessages(parsedMsgs);

      // Set latest citations in right panel from last assistant turn
      const lastAssistant = [...parsedMsgs].reverse().find((m) => m.role === 'assistant');
      if (lastAssistant) {
        setLatestRetrieval(lastAssistant.retrieval);
        setLatestLatency(lastAssistant.latency);
      }
    } catch (e) {
      console.error('Failed to load conversation messages', e);
    }
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    setActiveCitation(null);
    loadConversationMessages(id);
  };

  const handleNewChat = async () => {
    try {
      const newConv = await createConversation('New Chat');
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
      setMessages([]);
      setActiveCitation(null);
      setLatestRetrieval(null);
      setLatestLatency(null);
    } catch (e) {
      setActiveConversationId(null);
      setMessages([]);
      setActiveCitation(null);
      setLatestRetrieval(null);
      setLatestLatency(null);
    }
  };

  /**
   * Connects to the real-time Server-Sent Events stream for an ingestion job.
   */
  const connectSSE = (job: IngestionJobItem) => {
    if (eventSourcesRef.current.has(job.job_id)) {
      eventSourcesRef.current.get(job.job_id)!();
      eventSourcesRef.current.delete(job.job_id);
    }

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

  const handleUploadFile = async (file: File, title?: string) => {
    setIsIngesting(true);
    try {
      const job = await uploadFile(file, 'default', title);
      connectSSE(job);
      await loadDocuments();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleIngestUrl = async (url: string, title?: string) => {
    setIsIngesting(true);
    try {
      const job = await ingestUrl(url, 'default', title);
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

  const handleDeleteDocument = async (id: string) => {
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

      const response = await queryRAG(
        text,
        historyPayload,
        'default',
        selectedScope,
        activeConversationId || undefined
      );

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        latency_seconds: response.latency_seconds,
        has_sufficient_context: response.has_sufficient_context,
        retrieval: response.retrieval,
        latency: response.latency
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLatestRetrieval(response.retrieval);
      setLatestLatency(response.latency);

      // If a new conversation_id was returned, refresh conversations list
      if (response.conversation_id && response.conversation_id !== activeConversationId) {
        setActiveConversationId(response.conversation_id);
        loadConversations();
      }
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Execution Notice: ${err.message || 'Failed to complete query synthesis.'}`
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Derive active conversation title
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const activeTitle = activeConversation ? activeConversation.title : (messages.length > 0 ? messages[0].content.slice(0, 50) : 'Knowledge Workspace');

  // Derive citations to show in Knowledge Intelligence panel (from last assistant message)
  const currentCitations = (() => {
    const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
    return lastAssistant?.citations || [];
  })();

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', position: 'relative' }}>
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          className="backdrop-mobile"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 1. Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onNewChat={handleNewChat}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onOpenCommandMenu={() => setCommandMenuOpen(true)}
        onOpenSettings={() => setSettingsModalOpen(true)}
        isOpenMobile={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
      />

      {/* 2. Main Center & Right Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, overflow: 'hidden' }}>
        {/* Chat / View Header */}
        <ChatHeader
          title={activeTitle}
          documents={documents}
          selectedDocumentIds={selectedScope}
          onSelectDocumentScope={setSelectedScope}
          onOpenSearch={() => setCommandMenuOpen(true)}
          onToggleTheme={() => setDarkMode(!darkMode)}
          darkMode={darkMode}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onClearChat={() => setMessages([])}
          showIntelligencePanel={showIntelligencePanel}
          onToggleIntelligencePanel={() => setShowIntelligencePanel(!showIntelligencePanel)}
        />

        {/* View Content Body */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}>
          {activeTab === 'chat' && (
            <>
              {/* Central Chat Workspace */}
              <ChatWorkspace
                messages={messages}
                onSendMessage={handleSendMessage}
                isLoading={isChatLoading}
                selectedScopeIds={selectedScope}
                documents={documents}
                onOpenUpload={() => setUploadModalOpen(true)}
                onSelectCitation={(cit) => {
                  setActiveCitation(cit);
                  setShowIntelligencePanel(true);
                }}
              />

              {/* Right Knowledge Intelligence Panel */}
              {showIntelligencePanel && (
                <KnowledgeIntelligencePanel
                  citations={currentCitations}
                  retrievalMetadata={latestRetrieval}
                  latencyData={latestLatency}
                  activeCitation={activeCitation}
                  onSelectCitation={setActiveCitation}
                  onCloseMobile={() => setShowIntelligencePanel(false)}
                />
              )}
            </>
          )}

          {activeTab === 'documents' && (
            <DocumentsView
              documents={documents}
              onDeleteDocument={handleDeleteDocument}
              onOpenUploadModal={() => setUploadModalOpen(true)}
              onQueryDocumentInChat={(docId) => {
                setSelectedScope([docId]);
                setActiveTab('chat');
              }}
            />
          )}

          {activeTab === 'ingestion' && (
            <IngestionView
              activeJobs={activeJobs}
              onRetryJob={handleRetryJob}
              onOpenUploadModal={() => setUploadModalOpen(true)}
            />
          )}

          {activeTab === 'sources' && (
            <SourcesView
              documents={documents}
              onOpenUploadModal={() => setUploadModalOpen(true)}
              onFilterByCategory={(type) => {
                setActiveTab('documents');
              }}
            />
          )}
        </div>
      </div>

      {/* Upload Modal */}
      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUploadFile={handleUploadFile}
        onIngestUrl={handleIngestUrl}
        isLoading={isIngesting}
      />

      {/* Command Menu Modal */}
      <CommandMenuModal
        isOpen={commandMenuOpen}
        onClose={() => setCommandMenuOpen(false)}
        onNewChat={handleNewChat}
        onNavigate={setActiveTab}
        onOpenUpload={() => setUploadModalOpen(true)}
        onToggleTheme={() => setDarkMode(!darkMode)}
        darkMode={darkMode}
        documents={documents}
        onSelectDocument={(docId) => {
          setSelectedScope([docId]);
          setActiveTab('chat');
        }}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        health={health}
        darkMode={darkMode}
        onToggleTheme={() => setDarkMode(!darkMode)}
      />
    </div>
  );
};
