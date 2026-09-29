import React from 'react';
import { Database, Sun, Moon, Sparkles, BookOpen } from 'lucide-react';
import { SystemHealth } from '../types';

interface HeaderProps {
  health: SystemHealth | null;
  darkMode: boolean;
  onToggleTheme: () => void;
  documentCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  darkMode,
  onToggleTheme,
  documentCount
}) => {
  return (
    <header className="glass-panel" style={{ margin: '1rem', padding: '0.75rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'var(--accent-gradient)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          boxShadow: '0 2px 10px rgba(99, 102, 241, 0.4)'
        }}>
          <Sparkles size={20} />
        </div>
        <div>
          <h1 style={{ fontSize: '1.125rem', fontWeight: '700', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            Multi-Source RAG AI
            <span style={{
              fontSize: '0.6875rem',
              fontWeight: '600',
              textTransform: 'uppercase',
              padding: '2px 8px',
              borderRadius: '20px',
              background: 'var(--badge-bg)',
              color: 'var(--badge-text)',
              border: '1px solid rgba(99, 102, 241, 0.2)'
            }}>
              v1.0-Prod
            </span>
          </h1>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Grounded Knowledge Assistant with Verified Citations
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {health && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            fontSize: '0.75rem',
            background: 'var(--bg-input)',
            padding: '0.375rem 0.75rem',
            borderRadius: '8px',
            border: '1px solid var(--border-color)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)' }}></span>
              <span style={{ color: 'var(--text-secondary)' }}>LLM:</span>
              <span style={{ fontWeight: '600' }}>Groq ({health.llm_model.split('-')[0]})</span>
            </div>
            <div style={{ width: '1px', height: '14px', background: 'var(--border-color)' }}></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <Database size={13} style={{ color: 'var(--accent-primary)' }} />
              <span style={{ fontWeight: '600' }}>{health.indexed_chunks}</span>
              <span style={{ color: 'var(--text-muted)' }}>chunks</span>
            </div>
          </div>
        )}

        <button
          onClick={onToggleTheme}
          className="btn-secondary"
          style={{ padding: '0.5rem', borderRadius: '8px' }}
          title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </div>
    </header>
  );
};
