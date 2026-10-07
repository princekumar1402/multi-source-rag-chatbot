import React from 'react';
import {
  X,
  Settings,
  Database,
  Cpu,
  Layers,
  Sun,
  Moon,
  ShieldCheck,
  CheckCircle2,
  HardDrive
} from 'lucide-react';
import { SystemHealth } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: SystemHealth | null;
  darkMode: boolean;
  onToggleTheme: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  health,
  darkMode,
  onToggleTheme
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '1rem'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '520px',
          backgroundColor: 'var(--bg-surface)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-dropdown)',
          border: '1px solid var(--border-color)',
          overflow: 'hidden'
        }}
        className="animate-fade-in"
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <Settings size={18} style={{ color: 'var(--brand-blue)' }} />
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Platform Settings
            </h2>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Appearance Section */}
          <div>
            <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              APPEARANCE
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem 1rem',
                backgroundColor: 'var(--bg-surface-subtle)',
                borderRadius: '8px',
                border: '1px solid var(--border-color)'
              }}
            >
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Visual Theme
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Current: {darkMode ? 'Refined Dark Mode' : 'Light Cool-Gray (Primary Approved)'}
                </div>
              </div>

              <button
                onClick={onToggleTheme}
                className="gw-btn-secondary"
                style={{ padding: '0.4rem 0.75rem' }}
              >
                {darkMode ? <Sun size={15} /> : <Moon size={15} />}
                <span>{darkMode ? 'Use Light Mode' : 'Use Dark Mode'}</span>
              </button>
            </div>
          </div>

          {/* Infrastructure Health Section */}
          <div>
            <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              INFRASTRUCTURE TELEMETRY
            </div>

            <div
              style={{
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                backgroundColor: 'var(--bg-surface)',
                fontSize: '0.8125rem'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.625rem 0.875rem', borderBottom: '1px solid var(--border-color)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>FastAPI Gateway:</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--success)', fontWeight: 600 }}>
                  <CheckCircle2 size={13} />
                  <span>Healthy & Streaming Ready</span>
                </span>
              </div>

              {health && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.625rem 0.875rem', borderBottom: '1px solid var(--border-color)' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>LLM Synthesis:</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {health.llm_provider} ({health.llm_model})
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.625rem 0.875rem', borderBottom: '1px solid var(--border-color)' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Dense Embeddings:</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {health.embedding_provider} ({health.embedding_model})
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.625rem 0.875rem', borderBottom: '1px solid var(--border-color)' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Hybrid Vector Index:</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {health.vector_store} + BM25 Lexical
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.625rem 0.875rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Indexed Chunks:</span>
                    <span style={{ fontWeight: 700, color: 'var(--brand-blue)' }}>
                      {health.indexed_chunks} chunks
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'flex-end',
            backgroundColor: 'var(--bg-surface-subtle)'
          }}
        >
          <button onClick={onClose} className="gw-btn-primary" style={{ padding: '0.5rem 1rem' }}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
