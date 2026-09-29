import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SourceInput } from './components/SourceInput';
import { DocumentList } from './components/DocumentList';
import { ChatView } from './components/ChatView';
import { DocumentItem, ChatMessage, SystemHealth } from './types';
import { fetchHealth, fetchDocuments, ingestUrl, uploadFile, deleteDocument, queryRAG } from './services/api';

export const App: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(true);

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

  const handleIngestUrl = async (url: string) => {
    setIsIngesting(true);
    try {
      await ingestUrl(url);
      await loadDocuments();
      await loadHealth();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleUploadFile = async (file: File) => {
    setIsIngesting(true);
    try {
      await uploadFile(file);
      await loadDocuments();
      await loadHealth();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
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

      const response = await queryRAG(text, historyPayload);

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
        content: `Error retrieving answer: ${err.message || 'Unknown error'}`
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
          />
        </div>
      </main>
    </div>
  );
};
