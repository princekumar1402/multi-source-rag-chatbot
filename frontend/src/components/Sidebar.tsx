import React from 'react';
import {
  MessageSquare,
  FileText,
  Layers,
  BookOpen,
  Plus,
  Command,
  Settings,
  Sparkles,
  ChevronRight,
  Database
} from 'lucide-react';
import { ConversationItem } from '../types';

export type ActiveNavTab = 'chat' | 'documents' | 'ingestion' | 'sources';

interface SidebarProps {
  activeTab: ActiveNavTab;
  onSelectTab: (tab: ActiveNavTab) => void;
  onNewChat: () => void;
  conversations: ConversationItem[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onOpenCommandMenu: () => void;
  onOpenSettings: () => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  onNewChat,
  conversations,
  activeConversationId,
  onSelectConversation,
  onOpenCommandMenu,
  onOpenSettings,
  isOpenMobile,
  onCloseMobile
}) => {
  return (
    <aside
      style={{
        width: 'var(--sidebar-width)',
        minWidth: 'var(--sidebar-width)',
        height: '100vh',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        userSelect: 'none',
        zIndex: 40
      }}
      className={isOpenMobile ? 'sidebar-mobile-open' : ''}
    >
      {/* Top Header & Navigation */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* Brand Header */}
        <div style={{ padding: '1.25rem 1.25rem 1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              backgroundColor: 'var(--brand-blue)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 2px 4px rgba(37, 69, 211, 0.25)',
              flexShrink: 0
            }}
          >
            <Sparkles size={18} />
          </div>
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 800, letterSpacing: '0.04em', color: 'var(--text-primary)', lineHeight: 1.2 }}>
              GROUNDWORK
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: 500 }}>
              AI Knowledge Platform
            </div>
          </div>
        </div>

        {/* Primary Action: New Chat */}
        <div style={{ padding: '0 1rem 1rem 1rem' }}>
          <button
            onClick={() => {
              onNewChat();
              onSelectTab('chat');
              onCloseMobile?.();
            }}
            className="gw-btn-primary"
            style={{ width: '100%', padding: '0.625rem 0.875rem', fontSize: '0.8125rem' }}
          >
            <Plus size={16} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Nav Sections Scrollable */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 0.75rem' }}>
          {/* Section: WORKSPACE */}
          <div style={{ marginBottom: '1.25rem' }}>
            <div
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                letterSpacing: '0.06em',
                color: 'var(--text-subtle)',
                padding: '0.25rem 0.5rem',
                marginBottom: '0.25rem'
              }}
            >
              WORKSPACE
            </div>
            <button
              onClick={() => {
                onSelectTab('chat');
                onCloseMobile?.();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.5rem 0.625rem',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'chat' ? 'var(--bg-active-nav)' : 'transparent',
                color: activeTab === 'chat' ? 'var(--brand-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'chat' ? 600 : 500,
                fontSize: '0.8125rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease'
              }}
            >
              <MessageSquare size={16} />
              <span>Chat</span>
            </button>
          </div>

          {/* Section: KNOWLEDGE */}
          <div style={{ marginBottom: '1.25rem' }}>
            <div
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                letterSpacing: '0.06em',
                color: 'var(--text-subtle)',
                padding: '0.25rem 0.5rem',
                marginBottom: '0.25rem'
              }}
            >
              KNOWLEDGE
            </div>
            <button
              onClick={() => {
                onSelectTab('documents');
                onCloseMobile?.();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.5rem 0.625rem',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'documents' ? 'var(--bg-active-nav)' : 'transparent',
                color: activeTab === 'documents' ? 'var(--brand-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'documents' ? 600 : 500,
                fontSize: '0.8125rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                marginBottom: '2px'
              }}
            >
              <FileText size={16} />
              <span>Documents</span>
            </button>

            <button
              onClick={() => {
                onSelectTab('ingestion');
                onCloseMobile?.();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.5rem 0.625rem',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'ingestion' ? 'var(--bg-active-nav)' : 'transparent',
                color: activeTab === 'ingestion' ? 'var(--brand-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'ingestion' ? 600 : 500,
                fontSize: '0.8125rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
                marginBottom: '2px'
              }}
            >
              <Layers size={16} />
              <span>Ingestion</span>
            </button>

            <button
              onClick={() => {
                onSelectTab('sources');
                onCloseMobile?.();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.5rem 0.625rem',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: activeTab === 'sources' ? 'var(--bg-active-nav)' : 'transparent',
                color: activeTab === 'sources' ? 'var(--brand-blue)' : 'var(--text-secondary)',
                fontWeight: activeTab === 'sources' ? 600 : 500,
                fontSize: '0.8125rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease'
              }}
            >
              <BookOpen size={16} />
              <span>Sources</span>
            </button>
          </div>

          {/* Section: RECENT CONVERSATIONS */}
          <div style={{ marginBottom: '1rem' }}>
            <div
              style={{
                fontSize: '0.6875rem',
                fontWeight: 700,
                letterSpacing: '0.06em',
                color: 'var(--text-subtle)',
                padding: '0.25rem 0.5rem',
                marginBottom: '0.25rem'
              }}
            >
              RECENT CONVERSATIONS
            </div>

            {conversations.length === 0 ? (
              <div
                style={{
                  padding: '0.5rem 0.625rem',
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)'
                }}
              >
                No recent conversations
              </div>
            ) : (
              conversations.map((conv) => {
                const isSelected = activeConversationId === conv.id;
                return (
                  <button
                    key={conv.id}
                    onClick={() => {
                      onSelectConversation(conv.id);
                      onSelectTab('chat');
                      onCloseMobile?.();
                    }}
                    style={{
                      width: '100%',
                      display: 'block',
                      padding: '0.45rem 0.625rem',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: isSelected ? 'var(--bg-surface-subtle)' : 'transparent',
                      color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                      fontWeight: isSelected ? 600 : 400,
                      fontSize: '0.8125rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      transition: 'background-color 0.1s ease',
                      marginBottom: '2px'
                    }}
                    title={conv.title}
                  >
                    {conv.title}
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Bottom Footer Actions & User */}
      <div style={{ borderTop: '1px solid var(--border-color)', padding: '0.75rem 0.75rem' }}>
        <button
          onClick={onOpenCommandMenu}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '0.625rem',
            padding: '0.45rem 0.625rem',
            borderRadius: '6px',
            border: 'none',
            background: 'transparent',
            color: 'var(--text-secondary)',
            fontSize: '0.8125rem',
            cursor: 'pointer',
            textAlign: 'left',
            marginBottom: '2px'
          }}
        >
          <Command size={15} style={{ color: 'var(--text-muted)' }} />
          <span>Command menu</span>
        </button>

        <button
          onClick={onOpenSettings}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '0.625rem',
            padding: '0.45rem 0.625rem',
            borderRadius: '6px',
            border: 'none',
            background: 'transparent',
            color: 'var(--text-secondary)',
            fontSize: '0.8125rem',
            cursor: 'pointer',
            textAlign: 'left',
            marginBottom: '0.5rem'
          }}
        >
          <Settings size={15} style={{ color: 'var(--text-muted)' }} />
          <span>Settings</span>
        </button>

        {/* User Card */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.625rem',
            padding: '0.45rem 0.625rem',
            borderRadius: '6px',
            backgroundColor: 'var(--bg-surface-subtle)',
            marginTop: '0.25rem'
          }}
        >
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: '50%',
              backgroundColor: '#bfdbfe',
              color: '#1e40af',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.6875rem',
              fontWeight: 700,
              flexShrink: 0
            }}
          >
            AS
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Alex Student
            </div>
            <div style={{ fontSize: '0.625rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--success)' }}></span>
              <span>Online</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
