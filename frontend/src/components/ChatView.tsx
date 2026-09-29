import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Loader2, Info } from 'lucide-react';
import { ChatMessage } from '../types';
import { CitationCard } from './CitationCard';

interface ChatViewProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => Promise<void>;
  isLoading: boolean;
  hasDocuments: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  onSendMessage,
  isLoading,
  hasDocuments
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input.trim();
    setInput('');
    await onSendMessage(text);
  };

  return (
    <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Messages Scroll Area */}
      <div style={{ flex: 1, padding: '1.25rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {messages.length === 0 ? (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            color: 'var(--text-muted)',
            padding: '2rem'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'rgba(99, 102, 241, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-primary)',
              marginBottom: '1rem'
            }}>
              <Bot size={24} />
            </div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              Ask anything about your knowledge base
            </h3>
            <p style={{ fontSize: '0.8125rem', marginTop: '0.5rem', maxWidth: '400px' }}>
              {hasDocuments
                ? 'Answers are grounded strictly in your ingested sources with verified page and timestamp citations.'
                : 'Please ingest a website or YouTube video to begin chatting.'}
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                gap: '0.875rem',
                alignItems: 'flex-start',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row'
              }}
            >
              {/* Avatar */}
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: msg.role === 'user' ? 'var(--accent-gradient)' : 'var(--bg-input)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                border: '1px solid var(--border-color)',
                flexShrink: 0
              }}>
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} style={{ color: 'var(--accent-primary)' }} />}
              </div>

              {/* Message Content */}
              <div style={{
                maxWidth: '80%',
                background: msg.role === 'user' ? 'var(--accent-primary)' : 'var(--bg-input)',
                color: msg.role === 'user' ? '#ffffff' : 'var(--text-primary)',
                padding: '0.875rem 1rem',
                borderRadius: '12px',
                border: msg.role === 'user' ? 'none' : '1px solid var(--border-color)',
                fontSize: '0.875rem',
                lineHeight: '1.5'
              }}>
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                {/* Citations block for Assistant responses */}
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ marginTop: '0.875rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.625rem' }}>
                    <div style={{
                      fontSize: '0.75rem',
                      fontWeight: '600',
                      color: 'var(--text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      marginBottom: '0.375rem'
                    }}>
                      Sources & Citations ({msg.citations.length})
                    </div>
                    {msg.citations.map((c, idx) => (
                      <CitationCard key={c.chunk_id} citation={c} index={idx} />
                    ))}
                  </div>
                )}

                {/* Latency badge */}
                {msg.latency_seconds !== undefined && (
                  <div style={{
                    marginTop: '0.5rem',
                    fontSize: '0.6875rem',
                    color: 'var(--text-muted)',
                    textAlign: 'right'
                  }}>
                    Generated in {msg.latency_seconds}s
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div style={{ display: 'flex', gap: '0.875rem', alignItems: 'center' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'var(--bg-input)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid var(--border-color)'
            }}>
              <Loader2 size={16} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Retrieving relevant context and generating grounded answer...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSubmit} style={{
        padding: '1rem',
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        gap: '0.75rem'
      }}>
        <input
          type="text"
          className="input-field"
          placeholder={hasDocuments ? "Ask a question about your knowledge..." : "Add a source first to ask questions"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading || !hasDocuments}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={isLoading || !input.trim() || !hasDocuments}
          style={{ opacity: isLoading || !input.trim() || !hasDocuments ? 0.6 : 1 }}
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
};
