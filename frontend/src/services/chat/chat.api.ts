import globalConfig from "@/configs";

/**
 * Create a chat task and get stream URL
 */
export const createChatTask = async ({
  botId,
  sessionToken,
  message,
  language = 'vi',
}: {
  botId: string;
  sessionToken: string;
  message: string;
  language?: string;
}) => {
  const response = await fetch(
    `${globalConfig.apiUrl}/api/v1/chat/ask`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        bot_id: botId,
        session_token: sessionToken,
        message,
        language,
      }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to create chat task');
  }

  return response.json();
};

/**
 * Stream chat task events via SSE
 */
export const streamChat = async ({
  taskId,
  onEvent,
  onComplete,
  onError,
}: {
  taskId: string;
  onEvent?: (event: string, data: Record<string, unknown>) => void;
  onComplete?: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
}) => {
  const eventSource = new EventSource(
    `${globalConfig.apiUrl}/api/v1/chat/stream/${taskId}`
  );

  eventSource.addEventListener('connected', (e) => {
    const data = JSON.parse(e.data);
    onEvent?.('connected', data);
  });

  eventSource.addEventListener('update', (e) => {
    const data = JSON.parse(e.data);
    onEvent?.('update', data);
  });

  eventSource.addEventListener('completed', (e) => {
    const data = JSON.parse(e.data);
    onComplete?.(data);
    eventSource.close();
  });

  eventSource.addEventListener('failed', (e) => {
    const data = JSON.parse(e.data);
    onError?.(data.error || 'Task failed');
    eventSource.close();
  });

  eventSource.addEventListener('error', () => {
    onError?.('Connection error');
    eventSource.close();
  });

  // Return cleanup function
  return () => {
    eventSource.close();
  };
};

/**
 * Create a chat session
 */
export const createSession = async (botId: string) => {
  const response = await fetch(
    `${globalConfig.apiUrl}/api/v1/chat/sessions`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        bot_id: botId,
      }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to create session');
  }

  return response.json();
};

/**
 * Close a chat session
 */
export const closeSession = async ({
  sessionToken,
  reason,
  durationSeconds,
}: {
  sessionToken: string;
  reason?: string;
  durationSeconds?: number;
}) => {
  const response = await fetch(
    `${globalConfig.apiUrl}/api/v1/chat/sessions/${sessionToken}/close`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        reason,
        duration_seconds: durationSeconds,
      }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to close session');
  }

  return response.json();
};