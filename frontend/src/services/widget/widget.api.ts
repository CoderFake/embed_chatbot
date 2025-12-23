import { globalConfig } from '@/config/global';

/**
 * Widget API Service
 * Handles widget configuration, initialization, and chat operations
 */

// ============================================================================
// Types
// ============================================================================

export interface WidgetPosition {
  horizontal: "left" | "right";
  vertical: "top" | "bottom";
  offset_x: number;
  offset_y: number;
}

export interface WidgetSize {
  width: number;
  height: number;
  mobile_width?: number;
  mobile_height?: number;
}

export interface HeaderColors {
  background: string;
  text: string;
  subtitle_text: string;
  border?: string;
  icon: string;
}

export interface BackgroundColors {
  main: string;
  chat_area: string;
  message_container: string;
}

export interface MessageColors {
  user_background: string;
  user_text: string;
  bot_background: string;
  bot_text: string;
  timestamp: string;
  link: string;
  code_background: string;
  code_text: string;
}

export interface InputColors {
  background: string;
  text: string;
  placeholder: string;
  border: string;
  border_focus: string;
  icon: string;
}

export interface ButtonColors {
  primary_background: string;
  primary_text: string;
  primary_hover: string;
  secondary_background: string;
  secondary_text: string;
  secondary_hover: string;
  launcher_background: string;
  launcher_icon: string;
  send_button: string;
  send_button_disabled: string;
}

export interface ScrollbarColors {
  thumb: string;
  thumb_hover: string;
  track: string;
}

export interface WidgetColors {
  header: HeaderColors;
  background: BackgroundColors;
  message: MessageColors;
  input: InputColors;
  button: ButtonColors;
  scrollbar: ScrollbarColors;
  error: string;
  success: string;
  warning: string;
  info: string;
  divider: string;
  shadow: string;
}

export interface WidgetButton {
  icon?: string;
  text?: string;
  size: number;
  show_notification_badge: boolean;
}

export interface WidgetHeader {
  title: string;
  subtitle?: string;
  avatar_url?: string;
  show_online_status: boolean;
  show_close_button: boolean;
}

export interface WidgetWelcomeMessage {
  enabled: boolean;
  message: string;
  quick_replies: string[];
}

export interface WidgetInput {
  placeholder: string;
  max_length: number;
  enable_file_upload: boolean;
  allowed_file_types: string[];
  max_file_size_mb: number;
  show_emoji_picker: boolean;
}

export interface WidgetBehavior {
  auto_open: boolean;
  auto_open_delay: number;
  minimize_on_outside_click: boolean;
  show_typing_indicator: boolean;
  enable_sound: boolean;
  persist_conversation: boolean;
}

export interface WidgetBranding {
  show_powered_by: boolean;
  company_name?: string;
  company_logo_url?: string;
  privacy_policy_url?: string;
  terms_url?: string;
}

export interface DisplayConfig {
  position: WidgetPosition;
  size: WidgetSize;
  colors: WidgetColors;
  button: WidgetButton;
  header: WidgetHeader;
  welcome_message: WidgetWelcomeMessage;
  input: WidgetInput;
  behavior: WidgetBehavior;
  branding: WidgetBranding;
  custom_css?: string;
  language: string;
  timezone: string;
}

export interface WidgetConfig {
  bot_id: string;
  bot_name: string;
  bot_key: string;
  language?: string;
  display_config: DisplayConfig;
  // Quick access fields
  welcome_message?: string;
  header_title?: string;
  header_subtitle?: string;
  avatar_url?: string;
  placeholder?: string;
  primary_color?: string;
}

export interface VisitorProfile {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
}

export interface WidgetInitResponse {
  visitor_id: string;
  session_id: string;
  session_token: string;
  visitor_profile: VisitorProfile;
}

export interface WidgetChatResponse {
  task_id: string;
  status: string;
  stream_url: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get complete widget configuration for a bot
 * Returns full display_config with all styling, behavior, and content settings
 */
export const getWidgetConfig = async (botId: string): Promise<WidgetConfig> => {
  const response = await fetch(
    `${globalConfig.apiUrl}/api/v1/widget/config/${botId}`
  );

  if (!response.ok) {
    throw new Error(`Failed to get widget config: ${response.statusText}`);
  }

  return response.json();
};

/**
 * Initialize widget session
 * Creates or finds visitor and session, returns session token for chat
 */
export const initWidget = async (
  botId: string,
  sessionToken: string
): Promise<WidgetInitResponse> => {
  const response = await fetch(`${globalConfig.apiUrl}/api/v1/widget/init`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      bot_id: botId,
      session_token: sessionToken,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to initialize widget: ${response.statusText}`);
  }

  return response.json();
};

/**
 * Send chat message via widget
 * Creates chat task and returns stream URL
 */
export const sendWidgetMessage = async (
  sessionToken: string,
  message: string,
  language: string = "vi"
): Promise<WidgetChatResponse> => {
  const response = await fetch(`${globalConfig.apiUrl}/api/v1/widget/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_token: sessionToken,
      message,
      language,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to send message: ${response.statusText}`);
  }

  return response.json();
};

/**
 * Stream chat response via SSE
 * Connects to task stream and handles events
 */
export const streamWidgetChat = (
  taskId: string,
  callbacks: {
    onConnected?: (data: Record<string, unknown>) => void;
    onUpdate?: (data: Record<string, unknown>) => void;
    onCompleted?: (data: Record<string, unknown>) => void;
    onFailed?: (error: Record<string, unknown>) => void;
    onError?: (error: string) => void;
  }
): (() => void) => {
  const eventSource = new EventSource(
    `${globalConfig.apiUrl}/api/v1/chat/stream/${taskId}`
  );

  eventSource.addEventListener("connected", (e) => {
    const data = JSON.parse(e.data);
    callbacks.onConnected?.(data);
  });

  eventSource.addEventListener("update", (e) => {
    const data = JSON.parse(e.data);
    callbacks.onUpdate?.(data);
  });

  eventSource.addEventListener("completed", (e) => {
    const data = JSON.parse(e.data);
    callbacks.onCompleted?.(data);
    eventSource.close();
  });

  eventSource.addEventListener("failed", (e) => {
    const data = JSON.parse(e.data);
    callbacks.onFailed?.(data);
    eventSource.close();
  });

  eventSource.addEventListener("error", () => {
    callbacks.onError?.("Connection error");
    eventSource.close();
  });

  // Return cleanup function
  return () => {
    eventSource.close();
  };
};

/**
 * Close widget session
 * Triggers visitor grading in background
 */
export const closeWidgetSession = async (
  sessionToken: string,
  reason?: string,
  durationSeconds?: number
): Promise<void> => {
  const response = await fetch(
    `${globalConfig.apiUrl}/api/v1/chat/sessions/${sessionToken}/close`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        reason,
        duration_seconds: durationSeconds,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to close session: ${response.statusText}`);
  }
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get color value from display config with fallback
 */
export const getColor = (
  config: DisplayConfig | undefined,
  path: string,
  fallback: string
): string => {
  if (!config) return fallback;

  const keys = path.split(".");
  let value: unknown = config;

  for (const key of keys) {
    if (value && typeof value === "object" && key in value) {
      value = (value as Record<string, unknown>)[key];
    } else {
      return fallback;
    }
  }

  return typeof value === "string" ? value : fallback;
};

/**
 * Generate unique session token
 */
export const generateSessionToken = (): string => {
  return `sess_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`;
};

/**
 * Check if widget should auto-open
 */
export const shouldAutoOpen = (config: DisplayConfig): boolean => {
  return config.behavior?.auto_open ?? false;
};

/**
 * Get auto-open delay in milliseconds
 */
export const getAutoOpenDelay = (config: DisplayConfig): number => {
  const delay = config.behavior?.auto_open_delay ?? 3;
  return delay * 1000;
};

/**
 * Apply custom CSS to document
 */
export const applyCustomCSS = (customCSS?: string): void => {
  if (!customCSS) return;

  const styleId = "chatbot-custom-css";
  let styleEl = document.getElementById(styleId);

  if (!styleEl) {
    styleEl = document.createElement("style");
    styleEl.id = styleId;
    document.head.appendChild(styleEl);
  }

  styleEl.textContent = customCSS;
};

/**
 * Remove custom CSS from document
 */
export const removeCustomCSS = (): void => {
  const styleEl = document.getElementById("chatbot-custom-css");
  if (styleEl) {
    styleEl.remove();
  }
};
