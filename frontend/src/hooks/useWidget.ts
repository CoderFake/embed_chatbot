import { useState, useEffect, useCallback } from 'react';
import {
  getWidgetConfig,
  initWidget,
  sendWidgetMessage,
  streamWidgetChat,
  closeWidgetSession,
  generateSessionToken,
  shouldAutoOpen,
  getAutoOpenDelay,
  applyCustomCSS,
  removeCustomCSS,
  type WidgetConfig,
  type WidgetInitResponse,
  type DisplayConfig,
} from '@/services/widget/widget.api';

interface UseWidgetConfigOptions {
  botId: string;
  autoInit?: boolean;
  onConfigLoaded?: (config: WidgetConfig) => void;
  onError?: (error: Error) => void;
}

interface UseWidgetConfigReturn {
  config: WidgetConfig | null;
  displayConfig: DisplayConfig | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch and manage widget configuration
 * Automatically loads display config and applies custom CSS
 */
export const useWidgetConfig = ({
  botId,
  autoInit = true,
  onConfigLoaded,
  onError,
}: UseWidgetConfigOptions): UseWidgetConfigReturn => {
  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchConfig = useCallback(async () => {
    if (!botId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getWidgetConfig(botId);
      setConfig(data);

      // Apply custom CSS if exists
      if (data.display_config?.custom_css) {
        applyCustomCSS(data.display_config.custom_css);
      }

      onConfigLoaded?.(data);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to load config');
      setError(error);
      onError?.(error);
    } finally {
      setLoading(false);
    }
  }, [botId, onConfigLoaded, onError]);

  useEffect(() => {
    if (autoInit) {
      fetchConfig();
    }

    // Cleanup: remove custom CSS on unmount
    return () => {
      removeCustomCSS();
    };
  }, [autoInit, fetchConfig]);

  return {
    config,
    displayConfig: config?.display_config || null,
    loading,
    error,
    refetch: fetchConfig,
  };
};

interface UseWidgetSessionOptions {
  botId: string;
  config?: WidgetConfig | null;
  onSessionCreated?: (session: WidgetInitResponse) => void;
  onError?: (error: Error) => void;
}

interface UseWidgetSessionReturn {
  session: WidgetInitResponse | null;
  sessionToken: string | null;
  loading: boolean;
  error: Error | null;
  initSession: () => Promise<void>;
  closeSession: (reason?: string, durationSeconds?: number) => Promise<void>;
}

/**
 * Hook to manage widget session
 * Handles session creation, persistence, and cleanup
 */
export const useWidgetSession = ({
  botId,
  config,
  onSessionCreated,
  onError,
}: UseWidgetSessionOptions): UseWidgetSessionReturn => {
  const [session, setSession] = useState<WidgetInitResponse | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  // Load session from localStorage if persist_conversation is enabled
  useEffect(() => {
    if (!config?.display_config?.behavior?.persist_conversation) return;

    const savedToken = localStorage.getItem(`chatbot_session_${botId}`);
    const savedSession = localStorage.getItem(`chatbot_session_data_${botId}`);

    if (savedToken && savedSession) {
      try {
        setSessionToken(savedToken);
        setSession(JSON.parse(savedSession));
      } catch (err) {
        console.error('Failed to parse saved session:', err);
      }
    }
  }, [botId, config]);

  const initSession = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = generateSessionToken();
      const data = await initWidget(botId, token);

      setSession(data);
      setSessionToken(token);

      // Save to localStorage if enabled
      if (config?.display_config?.behavior?.persist_conversation) {
        localStorage.setItem(`chatbot_session_${botId}`, token);
        localStorage.setItem(`chatbot_session_data_${botId}`, JSON.stringify(data));
      }

      onSessionCreated?.(data);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to init session');
      setError(error);
      onError?.(error);
    } finally {
      setLoading(false);
    }
  }, [botId, config, onSessionCreated, onError]);

  const closeSession = useCallback(
    async (reason?: string, durationSeconds?: number) => {
      if (!sessionToken) return;

      try {
        await closeWidgetSession(sessionToken, reason, durationSeconds);

        // Clear localStorage
        localStorage.removeItem(`chatbot_session_${botId}`);
        localStorage.removeItem(`chatbot_session_data_${botId}`);
        localStorage.removeItem(`chatbot_messages_${botId}`);

        setSession(null);
        setSessionToken(null);
      } catch (err) {
        console.error('Failed to close session:', err);
      }
    },
    [sessionToken, botId]
  );

  return {
    session,
    sessionToken,
    loading,
    error,
    initSession,
    closeSession,
  };
};

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface UseWidgetChatOptions {
  botId: string;
  sessionToken: string | null;
  config?: WidgetConfig | null;
  onMessageSent?: (message: Message) => void;
  onMessageReceived?: (message: Message) => void;
  onError?: (error: Error) => void;
}

interface UseWidgetChatReturn {
  messages: Message[];
  loading: boolean;
  streaming: boolean;
  error: Error | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
}

/**
 * Hook to manage chat messages
 * Handles sending, streaming, and persistence
 */
export const useWidgetChat = ({
  botId,
  sessionToken,
  config,
  onMessageSent,
  onMessageReceived,
  onError,
}: UseWidgetChatOptions): UseWidgetChatReturn => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [streaming, setStreaming] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  // Load messages from localStorage
  useEffect(() => {
    if (!config?.display_config?.behavior?.persist_conversation) return;

    const saved = localStorage.getItem(`chatbot_messages_${botId}`);
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch (err) {
        console.error('Failed to parse saved messages:', err);
      }
    }
  }, [botId, config]);

  // Save messages to localStorage
  useEffect(() => {
    if (!config?.display_config?.behavior?.persist_conversation) return;
    if (messages.length === 0) return;

    localStorage.setItem(`chatbot_messages_${botId}`, JSON.stringify(messages));
  }, [messages, botId, config]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionToken) {
        const error = new Error('No active session');
        setError(error);
        onError?.(error);
        return;
      }

      setLoading(true);
      setError(null);

      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev: Message[]) => [...prev, userMessage]);
      onMessageSent?.(userMessage);

      try {
        // Create chat task
        const { task_id } = await sendWidgetMessage(
          sessionToken,
          content,
          config?.language || 'vi'
        );

        setLoading(false);
        setStreaming(true);

        let botMessageContent = '';
        const botMessageId = `msg_${Date.now()}_bot`;

        // Stream response
        const cleanup = streamWidgetChat(task_id, {
          onUpdate: (data) => {
            // Handle streaming tokens
            if (data.token) {
              botMessageContent += (data.token as string);

              setMessages((prev: Message[]) => {
                const existing = prev.find((m: Message) => m.id === botMessageId);
                if (existing) {
                  return prev.map((m: Message) =>
                    m.id === botMessageId
                      ? { ...m, content: botMessageContent }
                      : m
                  );
                } else {
                  const newMessage: Message = {
                    id: botMessageId,
                    role: 'assistant',
                    content: botMessageContent,
                    timestamp: new Date().toISOString(),
                  };
                  return [...prev, newMessage];
                }
              });
            }
          },
          onCompleted: (data) => {
            setStreaming(false);

            const finalMessage: Message = {
              id: botMessageId,
              role: 'assistant',
              content: (data.response as string) || botMessageContent,
              timestamp: new Date().toISOString(),
            };

            setMessages((prev: Message[]) => {
              const filtered = prev.filter((m: Message) => m.id !== botMessageId);
              return [...filtered, finalMessage];
            });

            onMessageReceived?.(finalMessage);
            cleanup();
          },
          onFailed: (error) => {
            setStreaming(false);
            const err = new Error((error.error as string) || 'Chat failed');
            setError(err);
            onError?.(err);
            cleanup();
          },
          onError: (errorMsg) => {
            setStreaming(false);
            const err = new Error(errorMsg);
            setError(err);
            onError?.(err);
            cleanup();
          },
        });
      } catch (err) {
        setLoading(false);
        setStreaming(false);
        const error = err instanceof Error ? err : new Error('Failed to send message');
        setError(error);
        onError?.(error);
      }
    },
    [sessionToken, config, onMessageSent, onMessageReceived, onError]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(`chatbot_messages_${botId}`);
  }, [botId]);

  return {
    messages,
    loading,
    streaming,
    error,
    sendMessage,
    clearMessages,
  };
};

/**
 * Hook to manage auto-open behavior
 */
export const useWidgetAutoOpen = (
  config: WidgetConfig | null,
  onAutoOpen: () => void
) => {
  useEffect(() => {
    if (!config?.display_config) return;

    if (shouldAutoOpen(config.display_config)) {
      const delay = getAutoOpenDelay(config.display_config);
      const timer = setTimeout(onAutoOpen, delay);
      return () => clearTimeout(timer);
    }
  }, [config, onAutoOpen]);
};
