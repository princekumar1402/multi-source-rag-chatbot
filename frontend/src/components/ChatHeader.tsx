import React, { useState, useRef, useEffect } from 'react';
import {
  Search,
  MoreHorizontal,
  ChevronDown,
  Check,
  Sun,
  Moon,
  Menu,
  FileText,
  Layers,
  Sparkles,
  PanelRightOpen,
  PanelRightClose
} from 'lucide-react';
import { DocumentItem } from '../types';

interface ChatHeaderProps {
  title: string;
  documents: DocumentItem[];
  selectedDocumentIds: string[];
  onSelectDocumentScope: (docIds: string[]) => void;
  onOpenSearch: () => void;
  onToggleTheme: () => void;
  darkMode: boolean;
  onOpenMobileMenu?: () => void;
  onClearChat?: () => void;
  showIntelligencePanel?: boolean;
  onToggleIntelligencePanel?: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  title,
  documents,
  selectedDocumentIds,
  onSelectDocumentScope,
  onOpenSearch,
  onToggleTheme,
  darkMode,
  onOpenMobileMenu,
  onClearChat,
  showIntelligencePanel,
  onToggleIntelligencePanel
}) => {
  const [scopeMenuOpen, setScopeMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const scopeRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (scopeRef.current && !scopeRef.current.contains(e.target as Node)) {
        setScopeMenuOpen(false);
      }
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const readyDocuments = documents.filter((d) => d.status === 'ready');

  const getScopeLabel = () => {
    if (!selectedDocumentIds || selectedDocumentIds.length === 0) {
      return 'All knowledge';
    }
    if (selectedDocumentIds.length === 1) {
      const doc = documents.find((d) => d.id === selectedDocumentIds[0]);
      return doc ? `Using: ${doc.title}` : '1 document selected';
    }
    return `${selectedDocumentIds.length} documents selected`;
  };

  return (
    <header
      style={{
        height: '64px',
        minHeight: '64px',
        borderBottom: '1px solid var(--border-color)',
        backgroundColor: 'var(--bg-surface)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem',
        zIndex: 20
      }}
    >
      {/* Left: Mobile Toggle + Breadcrumb & Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
        {onOpenMobileMenu && (
          <button
            onClick={onOpenMobileMenu}
            className="gw-btn-secondary"
            style={{ padding: '0.4rem', border: 'none', display: 'none' }}
            id="mobile-menu-btn"
            title="Toggle Menu"
          >
            <Menu size={18} />
          </button>
        )}
        <div>
          <div
            style={{
              fontSize: '0.6875rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: 'var(--text-muted)',
              lineHeight: 1.2
            }}
          >
            GROUNDWORK / KNOWLEDGE WORKSPACE
          </div>
          <h1
            style={{
              fontSize: '1.0625rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              lineHeight: 1.3,
              marginTop: '1px',
              maxWidth: '450px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}
          >
            {title || 'Knowledge Workspace'}
          </h1>
        </div>
      </div>

      {/* Right Controls: Scope Selector, Search, Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
        {/* Document Scope Selector */}
        <div ref={scopeRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setScopeMenuOpen(!scopeMenuOpen)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.375rem 0.75rem',
              borderRadius: '20px',
              border: '1px solid var(--border-color)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              fontSize: '0.8125rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: 'var(--success)'
              }}
            />
            <span style={{ maxWidth: '170px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {getScopeLabel()}
            </span>
            <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
          </button>

          {scopeMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                width: '280px',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                boxShadow: 'var(--shadow-dropdown)',
                padding: '0.5rem',
                zIndex: 50
              }}
            >
              <div
                style={{
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  color: 'var(--text-muted)',
                  padding: '0.25rem 0.5rem',
                  marginBottom: '0.25rem'
                }}
              >
                RETRIEVAL SCOPE
              </div>

              {/* All knowledge option */}
              <button
                onClick={() => {
                  onSelectDocumentScope([]);
                  setScopeMenuOpen(false);
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.5rem 0.625rem',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: selectedDocumentIds.length === 0 ? 'var(--bg-active-nav)' : 'transparent',
                  color: selectedDocumentIds.length === 0 ? 'var(--brand-blue)' : 'var(--text-primary)',
                  fontWeight: selectedDocumentIds.length === 0 ? 600 : 400,
                  fontSize: '0.8125rem',
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Layers size={15} />
                  <span>All knowledge ({readyDocuments.length} ready)</span>
                </div>
                {selectedDocumentIds.length === 0 && <Check size={14} />}
              </button>

              <div style={{ height: '1px', backgroundColor: 'var(--border-color)', margin: '0.375rem 0' }} />

              {/* Individual Document Options */}
              <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                {readyDocuments.length === 0 ? (
                  <div style={{ padding: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    No ready documents available.
                  </div>
                ) : (
                  readyDocuments.map((doc) => {
                    const isSelected = selectedDocumentIds.includes(doc.id);
                    return (
                      <button
                        key={doc.id}
                        onClick={() => {
                          onSelectDocumentScope([doc.id]);
                          setScopeMenuOpen(false);
                        }}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.45rem 0.625rem',
                          borderRadius: '6px',
                          border: 'none',
                          backgroundColor: isSelected ? 'var(--bg-active-nav)' : 'transparent',
                          color: isSelected ? 'var(--brand-blue)' : 'var(--text-primary)',
                          fontWeight: isSelected ? 600 : 400,
                          fontSize: '0.8125rem',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                          <FileText size={14} style={{ flexShrink: 0, color: 'var(--text-muted)' }} />
                          <span
                            style={{
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              maxWidth: '180px'
                            }}
                          >
                            {doc.title}
                          </span>
                        </div>
                        {isSelected && <Check size={14} />}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Search Button */}
        <button
          onClick={onOpenSearch}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.375rem 0.625rem',
            borderRadius: '6px',
            border: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            fontSize: '0.8125rem',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
        >
          <Search size={14} style={{ color: 'var(--text-muted)' }} />
          <span>Search</span>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              padding: '1px 5px',
              borderRadius: '4px',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-muted)',
              marginLeft: '2px'
            }}
          >
            ⌘ K
          </span>
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          className="gw-btn-secondary"
          style={{ padding: '0.4rem', borderRadius: '6px' }}
          title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {darkMode ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        {/* Toggle Knowledge Intelligence Panel (Tablet/Mobile) */}
        {onToggleIntelligencePanel && (
          <button
            onClick={onToggleIntelligencePanel}
            className="gw-btn-secondary intelligence-toggle-btn"
            style={{ padding: '0.4rem', borderRadius: '6px', display: 'none' }}
            title="Toggle Knowledge Intelligence Panel"
          >
            {showIntelligencePanel ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
          </button>
        )}

        {/* More Actions Dropdown */}
        <div ref={moreRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setMoreMenuOpen(!moreMenuOpen)}
            className="gw-btn-secondary"
            style={{ padding: '0.4rem', borderRadius: '6px' }}
            title="More actions"
          >
            <MoreHorizontal size={15} />
          </button>

          {moreMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 6px)',
                right: 0,
                width: '180px',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                boxShadow: 'var(--shadow-dropdown)',
                padding: '0.375rem',
                zIndex: 50
              }}
            >
              <button
                onClick={() => {
                  onClearChat?.();
                  setMoreMenuOpen(false);
                }}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.625rem',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  fontSize: '0.8125rem',
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                Clear current chat
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
