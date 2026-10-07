import React, { useState, useRef, useEffect } from 'react';
import {
  Paperclip,
  ArrowUp,
  Sparkles,
  Zap,
  CheckCircle2,
  Loader2,
  FileText,
  Video,
  Globe,
  Table,
  FileSpreadsheet
} from 'lucide-react';
import { ChatMessage, Citation, DocumentItem, SourceType } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatWorkspaceProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => Promise<void>;
  isLoading: boolean;
  selectedScopeIds: string[];
  documents: DocumentItem[];
  onOpenUpload: () => void;
  onSelectCitation: (citation: Citation) => void;
  onToggleScopeDropdown?: () => void;
}

export const ChatWorkspace: React.FC<ChatWorkspaceProps> = ({
  messages,
  onSendMessage,
  isLoading,
  selectedScopeIds,
  documents,
  onOpenUpload,
  onSelectCitation
}) => {
  const [inputText, setInputText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    if (!inputText.trim() || isLoading) return;
    const text = inputText.trim();
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await onSendMessage(text);
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const getScopeInfo = () => {
    if (!selectedScopeIds || selectedScopeIds.length === 0) {
      return {
        label: 'Scope: All knowledge',
        tooltip: 'Searching all ingested documents and sources'
      };
    }
    if (selectedScopeIds.length === 1) {
      const doc = documents.find((d) => d.id === selectedScopeIds[0]);
      const title = doc ? doc.title : '1 source';
      const truncated = title.length > 22 ? `${title.slice(0, 20)}…` : title;
      return {
        label: `Using: ${truncated}`,
        tooltip: `Using: ${title}`
      };
    }
    return {
      label: `Using: ${selectedScopeIds.length} sources`,
      tooltip: `${selectedScopeIds.length} sources selected`
    };
  };

  const getSourceIcon = (type: SourceType) => {
    switch (type) {
      case 'youtube':
        return <Video size={13} style={{ color: '#ef4444' }} />;
      case 'pdf':
        return <FileText size={13} style={{ color: '#3b82f6' }} />;
      case 'docx':
        return <FileText size={13} style={{ color: '#6366f1' }} />;
      case 'csv':
        return <Table size={13} style={{ color: '#f59e0b' }} />;
      case 'xlsx':
        return <FileSpreadsheet size={13} style={{ color: '#10b981' }} />;
      default:
        return <Globe size={13} style={{ color: '#10b981' }} />;
    }
  };

  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg-app)',
        overflow: 'hidden',
        position: 'relative'
      }}
    >
      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.5rem 2rem',
          display: 'flex',
          flexDirection: 'column',
          maxWidth: '820px',
          width: '100%',
          margin: '0 auto'
        }}
      >
        {/* Session Meta Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '2rem',
            paddingBottom: '0.75rem',
            borderBottom: '1px solid var(--border-color)',
            fontSize: '0.6875rem',
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: 'var(--text-muted)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <Zap size={14} style={{ color: 'var(--brand-blue)' }} />
            <span>GROUNDED SESSION</span>
          </div>
          <div>UPDATED JUST NOW</div>
        </div>

        {/* Empty State / Welcome Queries */}
        {messages.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'flex-start',
              padding: '2rem 0'
            }}
          >
            <div
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                color: 'var(--text-muted)',
                marginBottom: '0.5rem'
              }}
            >
              PROMPT SUGGESTIONS
            </div>
            <h2
              style={{
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginBottom: '1.25rem'
              }}
            >
              Ask questions grounded in your multi-source knowledge base
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
              {[
                'What is the minimum attendance requirement, and are there any exceptions?',
                'Summarize the primary guidelines and policies from our documentation.',
                'What are the key technical specifications mentioned in the uploaded materials?'
              ].map((queryText, i) => (
                <button
                  key={i}
                  onClick={() => onSendMessage(queryText)}
                  style={{
                    padding: '0.875rem 1rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-primary)',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-surface-subtle)';
                    e.currentTarget.style.borderColor = 'var(--brand-blue)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-surface)';
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                  }}
                >
                  {queryText}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {messages.map((msg) => (
              <div key={msg.id} className="animate-fade-in">
                {msg.role === 'user' ? (
                  /* Research-style User Query */
                  <div>
                    <div
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        letterSpacing: '0.08em',
                        color: 'var(--text-muted)',
                        marginBottom: '0.5rem'
                      }}
                    >
                      YOU
                    </div>
                    <div
                      style={{
                        fontSize: '1.0625rem',
                        fontWeight: 500,
                        color: 'var(--text-primary)',
                        lineHeight: 1.55
                      }}
                    >
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  /* Research-style AI Grounded Response */
                  <div style={{ marginTop: '0.5rem' }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.375rem',
                        fontSize: '0.6875rem',
                        fontWeight: 700,
                        letterSpacing: '0.08em',
                        color: 'var(--brand-blue)',
                        marginBottom: '0.75rem'
                      }}
                    >
                      <Sparkles size={14} />
                      <span>GROUNDWORK AI · GROUNDED RESPONSE</span>
                    </div>

                    <div
                      style={{
                        fontSize: '0.9375rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.68
                      }}
                    >
                      <MarkdownRenderer content={msg.content} />
                    </div>

                    {/* Source Citation Pills */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          flexWrap: 'wrap',
                          marginTop: '1.25rem'
                        }}
                      >
                        {msg.citations.map((c, citIdx) => (
                          <button
                            key={c.chunk_id || citIdx}
                            onClick={() => onSelectCitation(c)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.375rem',
                              padding: '0.25rem 0.625rem',
                              borderRadius: '6px',
                              border: '1px solid var(--border-citation)',
                              backgroundColor: 'var(--bg-citation-pill)',
                              color: 'var(--brand-navy)',
                              fontSize: '0.75rem',
                              fontWeight: 500,
                              cursor: 'pointer',
                              transition: 'all 0.15s ease'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor = 'var(--brand-blue)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor = 'var(--border-citation)';
                            }}
                          >
                            <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                              [{String(citIdx + 1).padStart(2, '0')}]
                            </span>
                            {getSourceIcon(c.source_type)}
                            <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {c.source_title || c.file_name || 'Source'}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Live Streaming / Thinking Indicator */}
            {isLoading && (
              <div className="animate-fade-in" style={{ marginTop: '0.5rem' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    letterSpacing: '0.08em',
                    color: 'var(--brand-blue)',
                    marginBottom: '0.5rem'
                  }}
                >
                  <Sparkles size={14} />
                  <span>GROUNDWORK AI · SYNTHESIZING RESPONSE</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  <Loader2 size={16} className="animate-spin" style={{ color: 'var(--brand-blue)' }} />
                  <span>Retrieving sources and synthesizing grounded answer...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Chat Composer Section */}
      <div
        style={{
          padding: '0 2rem 1.25rem 2rem',
          maxWidth: '820px',
          width: '100%',
          margin: '0 auto',
          position: 'relative'
        }}
      >
        {/* Composer Card */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            boxShadow: 'var(--shadow-card)',
            padding: '0.75rem 1rem 0.625rem 1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem'
          }}
        >
          {/* Multiline Textarea */}
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask your knowledge base..."
            disabled={isLoading}
            rows={1}
            style={{
              width: '100%',
              border: 'none',
              outline: 'none',
              resize: 'none',
              backgroundColor: 'transparent',
              color: 'var(--text-primary)',
              fontSize: '0.9375rem',
              lineHeight: 1.5,
              maxHeight: '180px',
              minHeight: '24px'
            }}
          />

          {/* Bottom Action Row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.25rem'
            }}
          >
            {/* Left: Attachment + Scope Badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                onClick={onOpenUpload}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  borderRadius: '4px',
                  transition: 'color 0.15s ease'
                }}
                title="Attach source file or ingest URL"
              >
                <Paperclip size={17} />
              </button>

              {(() => {
                const scopeInfo = getScopeInfo();
                return (
                  <div
                    title={scopeInfo.tooltip}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.375rem',
                      fontSize: '0.75rem',
                      color: 'var(--text-secondary)',
                      backgroundColor: 'var(--bg-surface-subtle)',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      cursor: 'default'
                    }}
                  >
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{scopeInfo.label}</span>
                  </div>
                );
              })()}
            </div>

            {/* Right: Shortcut Hint + Send Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
              <span
                style={{
                  fontSize: '0.6875rem',
                  color: 'var(--text-subtle)',
                  fontWeight: 500
                }}
              >
                Shift + Enter
              </span>

              <button
                onClick={handleSubmit}
                disabled={!inputText.trim() || isLoading}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: inputText.trim() && !isLoading ? 'var(--brand-blue)' : 'var(--bg-surface-subtle)',
                  color: inputText.trim() && !isLoading ? '#ffffff' : 'var(--text-muted)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: inputText.trim() && !isLoading ? 'pointer' : 'not-allowed',
                  transition: 'all 0.15s ease'
                }}
                title="Send query"
              >
                {isLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <ArrowUp size={16} />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Footer Meta Row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginTop: '0.5rem',
            padding: '0 0.25rem',
            fontSize: '0.6875rem',
            color: 'var(--text-muted)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
            <span>Grounded answers only</span>
          </div>

          <div>Ready · Grounded answers</div>
        </div>
      </div>
    </div>
  );
};
