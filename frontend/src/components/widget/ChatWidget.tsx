/**
 * ChatWidget Component
 * Production-ready chatbot widget with full configuration support
 * 
 * Usage:
 * ```tsx
 * import ChatWidget from '@/components/widget/ChatWidget';
 * 
 * <ChatWidget botId="your-bot-id" />
 * ```
 */

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  useWidgetConfig,
  useWidgetSession,
  useWidgetChat,
  useWidgetAutoOpen,
} from '@/hooks/useWidget';
import { cn } from '@/lib/utils';

interface ChatWidgetProps {
  botId: string;
  className?: string;
  onError?: (error: Error) => void;
}

export default function ChatWidget({ botId, className, onError }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isMobile, setIsMobile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load widget configuration
  const { config, displayConfig, loading: configLoading, error: configError } = useWidgetConfig({
    botId,
    autoInit: true,
    onError,
  });

  // Initialize session
  const { session, sessionToken, initSession, closeSession } = useWidgetSession({
    botId,
    config,
    onError,
  });

  const {
    messages,
    loading: chatLoading,
    streaming,
    sendMessage,
  } = useWidgetChat({
    botId,
    sessionToken,
    config,
    onError,
  });

  useWidgetAutoOpen(config, () => {
    if (!isOpen) {
      handleOpen();
    }
  });

  // Detect mobile device
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Update unread count when closed
  useEffect(() => {
    if (!isOpen && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant') {
        setUnreadCount((prev) => prev + 1);
      }
    }
  }, [messages, isOpen]);

  const handleClose = useCallback(async () => {
    setIsOpen(false);

    const duration = startTime ? Math.floor((Date.now() - startTime) / 1000) : undefined;

    if (sessionToken) {
      await closeSession('user_closed', duration);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, startTime]);

  useEffect(() => {
    if (!isOpen || !displayConfig?.behavior?.minimize_on_outside_click) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (widgetRef.current && !widgetRef.current.contains(event.target as Node)) {
        handleClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, displayConfig?.behavior?.minimize_on_outside_click]);

  const handleOpen = async () => {
    setIsOpen(true);
    setStartTime(Date.now());
    setUnreadCount(0);

    if (displayConfig?.behavior?.enable_sound) {
      try {
        const audio = new Audio('/notification.mp3');
        audio.play().catch(() => {});
      } catch { /* ignore */ }
    }

    if (!session) {
      await initSession();
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;
    await sendMessage(content);
  };

  const handleQuickReply = (reply: string) => {
    handleSendMessage(reply);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!input.allowed_file_types.includes(fileExt)) {
      const errorMsg = `File type not allowed. Allowed types: ${input.allowed_file_types.join(', ')}`;
      console.error(errorMsg);
      if (onError) {
        onError(new Error(errorMsg));
      }
      return;
    }

    // Validate file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > input.max_file_size_mb) {
      const errorMsg = `File size exceeds ${input.max_file_size_mb}MB limit`;
      console.error(errorMsg);
      if (onError) {
        onError(new Error(errorMsg));
      }
      return;
    }

    // TODO: Upload file logic
    console.log('File selected:', file.name);
  };

  const handleEmojiClick = (emoji: string) => {
    const inputEl = document.querySelector<HTMLInputElement>('input[name="message"]');
    if (inputEl) {
      inputEl.value += emoji;
      inputEl.focus();
    }
  };

  const renderMessageContent = (content: string) => {
    // Parse markdown links: [text](url)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts = content.split(linkRegex);
    
    if (parts.length === 1) {
      // No links, check for code blocks
      const codeRegex = /`([^`]+)`/g;
      const codeParts = content.split(codeRegex);
      
      return codeParts.map((part, idx) => {
        if (idx % 2 === 1) {
          // Code block
          return (
            <code
              key={idx}
              className="px-1 py-0.5 rounded text-xs font-mono"
              style={{
                backgroundColor: colors.message.code_background,
                color: colors.message.code_text,
              }}
            >
              {part}
            </code>
          );
        }
        return part;
      });
    }

    return parts.map((part, idx) => {
      if (idx % 3 === 1) {
        // Link text
        return (
          <a
            key={idx}
            href={parts[idx + 1]}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: colors.message.link }}
            className="underline hover:opacity-80"
          >
            {part}
          </a>
        );
      } else if (idx % 3 === 2) {
        // URL (already rendered in link)
        return null;
      }
      return part;
    });
  };

  // Loading state
  if (configLoading) {
    return (
      <div className={cn('fixed bottom-5 right-5', className)}>
        <div className="w-14 h-14 rounded-full bg-gray-200 animate-pulse" />
      </div>
    );
  }

  // Error state
  if (configError || !config || !displayConfig) {
    console.error('Widget config error:', configError);
    return null;
  }

  const colors = displayConfig.colors;
  const position = displayConfig.position;
  const size = displayConfig.size;
  const header = displayConfig.header;
  const welcomeMsg = displayConfig.welcome_message;
  const input = displayConfig.input;
  const button = displayConfig.button;
  const behavior = displayConfig.behavior;
  const branding = displayConfig.branding;

  // Responsive size
  const widgetWidth = isMobile && size.mobile_width ? size.mobile_width : size.width;
  const widgetHeight = isMobile && size.mobile_height ? size.mobile_height : size.height;

  return (
    <>
      {/* Custom CSS injection */}
      {displayConfig.custom_css && (
        <style dangerouslySetInnerHTML={{ __html: displayConfig.custom_css }} />
      )}

      {/* Custom scrollbar styles */}
      <style>{`
        .widget-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .widget-scrollbar::-webkit-scrollbar-track {
          background: ${colors.scrollbar.track};
        }
        .widget-scrollbar::-webkit-scrollbar-thumb {
          background: ${colors.scrollbar.thumb};
          border-radius: 4px;
        }
        .widget-scrollbar::-webkit-scrollbar-thumb:hover {
          background: ${colors.scrollbar.thumb_hover};
        }
      `}</style>

      <div className={className} style={{ zIndex: 9999 }} ref={widgetRef}>
        {/* Launcher Button */}
        {!isOpen && (
          <button
            onClick={handleOpen}
            className={cn(
              'fixed rounded-full shadow-lg transition-transform hover:scale-110 active:scale-95 relative',
              className
            )}
            style={{
              [position.vertical]: `${position.offset_y}px`,
              [position.horizontal]: `${position.offset_x}px`,
              width: `${button.size}px`,
              height: `${button.size}px`,
              backgroundColor: colors.button.launcher_background,
              color: colors.button.launcher_icon,
              boxShadow: colors.shadow,
            }}
            aria-label="Open chat"
            title={button.text || 'Open chat'}
          >
            {button.icon ? (
              <span className="text-2xl">{button.icon}</span>
            ) : (
              <svg
                className="w-6 h-6 mx-auto"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
            )}

            {/* Notification Badge */}
            {button.show_notification_badge && unreadCount > 0 && (
              <span
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
                style={{
                  backgroundColor: colors.error,
                  color: '#fff',
                }}
              >
                {unreadCount}
              </span>
            )}
          </button>
        )}

        {/* Chat Window */}
        {isOpen && (
          <div
            className={cn(
              'fixed rounded-lg overflow-hidden flex flex-col',
              className
            )}
            style={{
              [position.vertical]: `${position.offset_y}px`,
              [position.horizontal]: `${position.offset_x}px`,
              width: `${widgetWidth}px`,
              height: `${widgetHeight}px`,
              backgroundColor: colors.background.main,
              boxShadow: colors.shadow,
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3"
              style={{
                backgroundColor: colors.header.background,
                color: colors.header.text,
                borderBottom: colors.header.border ? `1px solid ${colors.header.border}` : 'none',
              }}
            >
              <div className="flex items-center gap-3">
                <div className="relative">
                  {branding.company_logo_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={branding.company_logo_url}
                      alt="Company logo"
                      className="w-10 h-10 rounded-full object-cover"
                    />
                  ) : header.avatar_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={header.avatar_url}
                      alt="Bot avatar"
                      className="w-10 h-10 rounded-full object-cover"
                    />
                  ) : null}
                  
                  {/* Online Status Indicator */}
                  {header.show_online_status && (
                    <span
                      className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2"
                      style={{
                        backgroundColor: colors.success,
                        borderColor: colors.header.background,
                      }}
                      title="Online"
                    />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-sm">{header.title}</h3>
                  {header.subtitle && (
                    <p className="text-xs opacity-90" style={{ color: colors.header.subtitle_text }}>
                      {header.subtitle}
                    </p>
                  )}
                </div>
              </div>

              {header.show_close_button && (
                <button
                  onClick={handleClose}
                  className="p-1 rounded hover:bg-white/10 transition-colors"
                  style={{ color: colors.header.icon }}
                  aria-label="Close chat"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              )}
            </div>

            {/* Messages Area */}
            <div
              className="flex-1 overflow-y-auto p-4 space-y-4 widget-scrollbar"
              style={{ backgroundColor: colors.background.chat_area }}
            >
            {/* Welcome Message */}
            {messages.length === 0 && welcomeMsg.enabled && (
              <div className="space-y-3">
                <div
                  className="rounded-lg p-3 max-w-[80%]"
                  style={{
                    backgroundColor: colors.message.bot_background,
                    color: colors.message.bot_text,
                  }}
                >
                  <p className="text-sm">{welcomeMsg.message}</p>
                </div>

                {/* Quick Replies */}
                {welcomeMsg.quick_replies.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {welcomeMsg.quick_replies.map((reply, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleQuickReply(reply)}
                        className="px-3 py-2 rounded-full text-sm transition-colors"
                        style={{
                          backgroundColor: colors.button.secondary_background,
                          color: colors.button.secondary_text,
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = colors.button.secondary_hover;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = colors.button.secondary_background;
                        }}
                      >
                        {reply}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

              {/* Messages */}
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className="rounded-lg p-3 max-w-[80%]"
                    style={{
                      backgroundColor:
                        message.role === 'user'
                          ? colors.message.user_background
                          : colors.message.bot_background,
                      color:
                        message.role === 'user'
                          ? colors.message.user_text
                          : colors.message.bot_text,
                    }}
                  >
                    <div className="text-sm whitespace-pre-wrap">
                      {renderMessageContent(message.content)}
                    </div>
                    <p
                      className="text-xs mt-1 opacity-70"
                      style={{ color: colors.message.timestamp }}
                    >
                      {new Date(message.timestamp).toLocaleTimeString(
                        displayConfig.language || 'en',
                        { timeZone: displayConfig.timezone || 'UTC' }
                      )}
                    </p>
                  </div>
                </div>
              ))}

            {/* Typing Indicator */}
            {streaming && behavior.show_typing_indicator && (
              <div className="flex justify-start">
                <div
                  className="rounded-lg p-3"
                  style={{
                    backgroundColor: colors.message.bot_background,
                  }}
                >
                  <div className="flex gap-1">
                    <div
                      className="w-2 h-2 rounded-full animate-bounce"
                      style={{ backgroundColor: colors.message.bot_text, animationDelay: '0ms' }}
                    />
                    <div
                      className="w-2 h-2 rounded-full animate-bounce"
                      style={{ backgroundColor: colors.message.bot_text, animationDelay: '150ms' }}
                    />
                    <div
                      className="w-2 h-2 rounded-full animate-bounce"
                      style={{ backgroundColor: colors.message.bot_text, animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              </div>
            )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t" style={{ borderColor: colors.divider }}>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  const message = formData.get('message') as string;
                  handleSendMessage(message);
                  e.currentTarget.reset();
                }}
                className="flex gap-2 items-end"
              >
                <div className="flex-1 flex flex-col gap-2">
                  <input
                    name="message"
                    type="text"
                    placeholder={input.placeholder}
                    maxLength={input.max_length}
                    disabled={chatLoading || streaming}
                    className="w-full px-3 py-2 rounded-lg border outline-none transition-colors"
                    style={{
                      backgroundColor: colors.input.background,
                      color: colors.input.text,
                      borderColor: colors.input.border,
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = colors.input.border_focus;
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = colors.input.border;
                    }}
                  />
                  
                  {/* Action Buttons Row */}
                  <div className="flex gap-2">
                    {/* Emoji Picker */}
                    {input.show_emoji_picker && (
                      <div className="flex gap-1">
                        {['😊', '👍', '❤️', '😂', '🎉'].map((emoji) => (
                          <button
                            key={emoji}
                            type="button"
                            onClick={() => handleEmojiClick(emoji)}
                            className="text-lg hover:scale-125 transition-transform"
                            title="Add emoji"
                          >
                            {emoji}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* File Upload */}
                    {input.enable_file_upload && (
                      <>
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept={input.allowed_file_types.join(',')}
                          onChange={handleFileUpload}
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="p-2 rounded hover:bg-gray-100 transition-colors"
                          style={{ color: colors.input.icon }}
                          title="Upload file"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                            />
                          </svg>
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={chatLoading || streaming}
                  className="px-4 py-2 rounded-lg transition-all disabled:opacity-50 hover:scale-105"
                  style={{
                    backgroundColor:
                      chatLoading || streaming
                        ? colors.button.send_button_disabled
                        : colors.button.send_button,
                    color: colors.button.primary_text,
                  }}
                  onMouseEnter={(e) => {
                    if (!chatLoading && !streaming) {
                      e.currentTarget.style.backgroundColor = colors.button.primary_hover;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!chatLoading && !streaming) {
                      e.currentTarget.style.backgroundColor = colors.button.send_button;
                    }
                  }}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                </button>
              </form>
            </div>

            {/* Branding Footer */}
            {branding.show_powered_by && (
              <div
                className="px-4 py-2 text-center text-xs border-t flex items-center justify-center gap-2"
                style={{
                  color: colors.message.timestamp,
                  borderColor: colors.divider,
                }}
              >
                <span>Powered by {branding.company_name || 'Chatbot Platform'}</span>
                {(branding.privacy_policy_url || branding.terms_url) && (
                  <span>•</span>
                )}
                {branding.privacy_policy_url && (
                  <a
                    href={branding.privacy_policy_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                    style={{ color: colors.message.link }}
                  >
                    Privacy
                  </a>
                )}
                {branding.terms_url && (
                  <>
                    {branding.privacy_policy_url && <span>•</span>}
                    <a
                      href={branding.terms_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                      style={{ color: colors.message.link }}
                    >
                      Terms
                    </a>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
