export type MessageType = {
  message_id: string;
  message: string;
  response: string;
  metadata: {
    follow_up_questions: string[];
  };
};
export type SessionType = {
  session_id: string;
  title: string;
};

export type ChatHistoryType = {
  session_id: string;
  title: string;
  messages: MessageType[];
};

export type DisplayConfigType = {
  colors: {
    background: {
      chat_area: string;
      main: string;
    };
    button?: {
      launcher_background: string;
      primary_background: string;
      primary_text: string;
    };
    header?: {
      background: string;
      subtitle_text: string;
      text: string;
    };
    input?: {
      background: string;
      border: string;
      border_focus: string;
      text: string;
    };
    message?: {
      bot_background: string;
      bot_text: string;
      user_background: string;
      user_text: string;
    };
  };
  header: {
    subtitle: string;
    title: string;
  };
  position?: {
    horizontal: string;
    offset_x: number;
    offset_y: number;
    vertical: string;
  };
  size?: {
    height: number;
    width: number;
  };
  welcome_message?: {
    enabled: true;
    message: string;
    quick_replies: string[];
  };
};
export type ChatbotPropsType = {
  name: string;
  language: string;
  display_config: DisplayConfigType;
  collection_name?: string;
  bucket_name?: string;
  origin: string;
  sitemap_urls: string[];
  created_at?: string;
  updated_at?: string;
};
