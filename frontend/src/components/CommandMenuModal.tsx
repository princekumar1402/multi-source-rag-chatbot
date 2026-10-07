import React, { useState, useEffect } from 'react';
import {
  Search,
  MessageSquare,
  FileText,
  Layers,
  BookOpen,
  Plus,
  Sun,
  Moon,
  X,
  Upload
} from 'lucide-react';
import { DocumentItem } from '../types';

interface CommandMenuModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onNavigate: (tab: 'chat' | 'documents' | 'ingestion' | 'sources') => void;
  onOpenUpload: () => void;
  onToggleTheme: () => void;
  darkMode: boolean;
  documents: DocumentItem[];
  onSelectDocument: (docId: string) => void;
}

export const CommandMenuModal: React.FC<CommandMenuModalProps> = ({
  isOpen,
  onClose,
  onNewChat,
  onNavigate,
  onOpenUpload,
  onToggleTheme,
  darkMode,
  documents,
  onSelectDocument
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // open will be handled by parent
        }
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const matchedDocs = documents.filter((d) =>
    (d.title || '').toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '10vh',
        zIndex: 100
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-dropdown)',
          border: '1px solid var(--border-color)',
          overflow: 'hidden'
        }}
        className="animate-fade-in"
      >
        {/* Search input header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-color)'
          }}
        >
          <Search size={18} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search documents..."
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              backgroundColor: 'transparent',
              fontSize: '0.9375rem',
              color: 'var(--text-primary)'
            }}
          />
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '2px'
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Actions & Matched Items List */}
        <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '0.5rem' }}>
          {/* Quick Actions */}
          <div style={{ padding: '0.25rem 0.5rem', fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            ACTIONS
          </div>

          <button
            onClick={() => { onNewChat(); onNavigate('chat'); onClose(); }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '0.625rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-primary)',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              textAlign: 'left'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <Plus size={16} style={{ color: 'var(--brand-blue)' }} />
            <span>Create new chat session</span>
          </button>

          <button
            onClick={() => { onOpenUpload(); onClose(); }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '0.625rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-primary)',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              textAlign: 'left'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <Upload size={16} style={{ color: 'var(--brand-blue)' }} />
            <span>Add document or URL</span>
          </button>

          <button
            onClick={() => { onToggleTheme(); onClose(); }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '0.625rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-primary)',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              textAlign: 'left'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            {darkMode ? <Sun size={16} style={{ color: '#f59e0b' }} /> : <Moon size={16} style={{ color: '#6366f1' }} />}
            <span>Toggle theme ({darkMode ? 'Light' : 'Dark'} mode)</span>
          </button>

          <button
            onClick={() => { onNavigate('documents'); onClose(); }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '0.625rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-primary)',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              textAlign: 'left'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <FileText size={16} style={{ color: 'var(--text-muted)' }} />
            <span>Go to Documents</span>
          </button>

          {/* Matched Documents */}
          {matchedDocs.length > 0 && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ padding: '0.25rem 0.5rem', fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                MATCHED DOCUMENTS ({matchedDocs.length})
              </div>

              {matchedDocs.slice(0, 5).map((d) => (
                <button
                  key={d.id}
                  onClick={() => {
                    onSelectDocument(d.id);
                    onNavigate('chat');
                    onClose();
                  }}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-primary)',
                    fontSize: '0.8125rem',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                    <FileText size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {d.title}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--brand-blue)', fontWeight: 600 }}>
                    Scope to chat
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
