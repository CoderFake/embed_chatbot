/**
 * Standalone Chatbot Widget - Pure JavaScript (No Server Required)
 * Embed directly into any website without needing a separate widget server
 */

(function() {
  'use strict';

  const DEFAULT_API_URL = 'http://localhost:18000';

  class ChatbotWidget {
    constructor(config) {
      this.botId = config.botId;
      this.apiUrl = config.apiUrl || DEFAULT_API_URL;
      this.config = null;
      this.session = null;
      this.messages = [];
      this.isOpen = false;
      this.isStreaming = false;
      this.currentEventSource = null;
      
      this.pendingAssistantContent = '';
      this.needsRender = false;
      this.renderLoopId = null;
      
      this.init();
    }
    
    startRenderLoop() {
      if (this.renderLoopId) return;
      
      const loop = () => {
        if (this.needsRender && this.isStreaming) {
          const messagesContainer = this.shadowRoot.querySelector('#chatbot-messages');
          if (messagesContainer) {
            const messageElements = messagesContainer.querySelectorAll('.chatbot-message.assistant');
            const lastAssistantMsg = messageElements[messageElements.length - 1];
            
            if (lastAssistantMsg) {
              const contentEl = lastAssistantMsg.querySelector('.chatbot-message-content > div');
              if (contentEl) {
                contentEl.innerHTML = this.renderMarkdown(this.pendingAssistantContent);
                this.scrollToBottom();
              }
            }
          }
          this.needsRender = false;
        }
        
        if (this.isStreaming) {
          this.renderLoopId = requestAnimationFrame(loop);
        } else {
          this.renderLoopId = null;
        }
      };
      
      this.renderLoopId = requestAnimationFrame(loop);
    }

    async init() {
      try {
        await this.loadConfig();
        this.loadSession();
        this.render();
        this.attachEventListeners();
        
        const displayConfig = this.config.display_config || {};
        const behaviorConfig = displayConfig.behavior || {};
        if (behaviorConfig.auto_open === true) {
          const delay = (behaviorConfig.auto_open_delay || 3) * 1000;
          setTimeout(() => {
            this.open();
          }, delay);
        }
      } catch (error) {
        console.error('Failed to initialize chatbot:', error);
      }
    }

    async loadConfig() {
      const response = await fetch(`${this.apiUrl}/api/v1/widget/config/${this.botId}`);
      if (!response.ok) throw new Error('Failed to load config');
      this.config = await response.json();
    }

    loadSession() {
      const saved = localStorage.getItem(`chatbot_session_${this.botId}`);
      if (saved) {
        this.session = JSON.parse(saved);
        const savedMessages = localStorage.getItem(`chatbot_messages_${this.botId}`);
        if (savedMessages) {
          this.messages = JSON.parse(savedMessages);
        }
      }
    }

    saveSession() {
      localStorage.setItem(`chatbot_session_${this.botId}`, JSON.stringify(this.session));
      localStorage.setItem(`chatbot_messages_${this.botId}`, JSON.stringify(this.messages));
    }

    async createSession() {
      const response = await fetch(`${this.apiUrl}/api/v1/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bot_id: this.botId
        })
      });
      
      if (!response.ok) throw new Error('Failed to create session');
      this.session = await response.json();
      this.saveSession();
      
      const displayConfig = this.config.display_config || {};
      const welcomeMsg = displayConfig.welcome_message || {};
      const welcomeText = welcomeMsg.enabled !== false ? (welcomeMsg.message || this.config.welcome_message) : null;
      
      if (welcomeText) {
        this.messages.push({
          id: this.generateId(),
          role: 'assistant',
          content: welcomeText,
          timestamp: new Date().toISOString()
        });
        this.saveSession();
      }
    }

    async sendMessage(message) {
      if (!this.session) return;

  
      const conversationHistory = this.messages
        .filter(msg => msg.role !== 'system')
        .slice(-20)
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      const userMsg = {
        id: this.generateId(),
        role: 'user',
        content: message,
        timestamp: new Date().toISOString()
      };
      this.messages.push(userMsg);
      this.updateMessages();
      this.saveSession();

      this.pendingAssistantContent = '';
      
      this.isStreaming = true;
      this.updateMessages();

      try {
        const taskResponse = await fetch(`${this.apiUrl}/api/v1/widget/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_token: this.session.session_token,
            message: message,
            conversation_history: conversationHistory
          })
        });

        if (!taskResponse.ok) {
          const error = await taskResponse.json().catch(() => ({ detail: 'Unknown error' }));
          throw new Error(error.detail || 'Failed to send message');
        }
        
        const taskData = await taskResponse.json();

        let assistantMsg = {
          id: this.generateId(),
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString()
        };
        
        const eventSource = new EventSource(`${this.apiUrl}${taskData.stream_url}`);
        this.currentEventSource = eventSource;
        
        this.pendingAssistantContent = '';
        this.startRenderLoop();
        
        const timeoutId = setTimeout(async () => {
          if (this.isStreaming && !assistantMsg.content) {
            try {
              const pollResponse = await fetch(`${this.apiUrl}/api/v1/chat/task/${taskData.task_id}`);
              if (pollResponse.ok) {
                const taskStatus = await pollResponse.json();
                if (taskStatus.status === 'completed' && taskStatus.result?.response) {
                  assistantMsg.content = taskStatus.result.response;
                  if (!this.messages.includes(assistantMsg)) {
                    this.messages.push(assistantMsg);
                  }
                  this.updateMessages();
                  this.saveSession();
                }
              }
            } catch (pollError) {
              console.error('[SSE] Polling failed:', pollError);
            }
            if (eventSource) {
              eventSource.close();
            }
            this.currentEventSource = null;
            this.isStreaming = false;
            this.updateMessages();
          }
        }, 30000);
        
        eventSource.addEventListener('connected', (e) => {
          
          setTimeout(async () => {
            if (this.isStreaming && !assistantMsg.content) {
              try {
                const checkResponse = await fetch(`${this.apiUrl}/api/v1/chat/task/${taskData.task_id}`);
                if (checkResponse.ok) {
                  const taskStatus = await checkResponse.json();
                  if (taskStatus.status === 'completed' && taskStatus.result?.response) {
                    assistantMsg.content = taskStatus.result.response;
                    if (!this.messages.includes(assistantMsg)) {
                      this.messages.push(assistantMsg);
                    }
                    this.updateMessages();
                    this.saveSession();
                    clearTimeout(timeoutId);
                    eventSource.close();
                    this.currentEventSource = null;
                    this.isStreaming = false;
                  }
                }
              } catch (checkError) {
              }
            }
          }, 1000);
        });
        

        let assistantMsgElement = null;
        
        eventSource.addEventListener('token', (e) => {
            try {
            const data = JSON.parse(e.data);
            if (data.token) {
              assistantMsg.content += data.token;
              this.pendingAssistantContent = assistantMsg.content;
              
              if (!assistantMsgElement) {
                if (!this.messages.includes(assistantMsg)) {
                  this.messages.push(assistantMsg);
                  
                }
                if (this.shadowRoot) {
                  const messagesContainer = this.shadowRoot.querySelector('#chatbot-messages');
                  if (messagesContainer) {
                    const messageElements = messagesContainer.querySelectorAll('.chatbot-message.assistant');
                    assistantMsgElement = messageElements[messageElements.length - 1];
                  }
                }
              }
              
              this.needsRender = true;
            }
          } catch (err) {
            console.error('Failed to parse token event:', err);
          }
        });
        
        eventSource.addEventListener('sources', (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.sources) {
              assistantMsg.sources = data.sources;
            }
          } catch (err) {
            console.error('Failed to parse sources event:', err);
          }
        });
        
        eventSource.addEventListener('progress', (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.content) {
              assistantMsg.content += data.content;
              if (!this.messages.includes(assistantMsg)) {
                this.messages.push(assistantMsg);
              }
              this.messages[this.messages.length - 1] = assistantMsg;
              this.updateMessages();
            }
          } catch (err) {
            console.error('Failed to parse progress event:', err);
          }
        });
        
        eventSource.addEventListener('done', (e) => {
          try {
            const data = JSON.parse(e.data);
            if (data.response) {
              assistantMsg.content = data.response;
              if (!this.messages.includes(assistantMsg)) {
                this.messages.push(assistantMsg);
              }
              this.messages[this.messages.length - 1] = assistantMsg;
              this.updateMessages();
              this.saveSession();
            }
          } catch (err) {
            console.error('Failed to parse done event:', err);
          }
          eventSource.close();
          this.currentEventSource = null;
          this.isStreaming = false;
          this.updateMessages();
        });
        
        eventSource.addEventListener('completed', (e) => {
          clearTimeout(timeoutId);
          try {
            const data = JSON.parse(e.data);
            const response = data.response || data.result?.response;
            if (response) {
              assistantMsg.content = response;
              if (!this.messages.includes(assistantMsg)) {
                this.messages.push(assistantMsg);
              }
              this.messages[this.messages.length - 1] = assistantMsg;
              this.updateMessages();
              this.saveSession();
            }
          } catch (err) {
            console.error('Failed to parse completed event:', err);
          }
          eventSource.close();
          this.currentEventSource = null;
          this.isStreaming = false;
          this.updateMessages();
        });
        
        eventSource.addEventListener('failed', (e) => {
          try {
            const data = JSON.parse(e.data);
            assistantMsg.content = 'Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.';
            if (!this.messages.includes(assistantMsg)) {
              this.messages.push(assistantMsg);
            }
            this.messages[this.messages.length - 1] = assistantMsg;
            this.updateMessages();
            this.saveSession();
          } catch (err) {
            console.error('Failed to parse error event:', err);
          }
          eventSource.close();
          this.currentEventSource = null;
          this.isStreaming = false;
          this.updateMessages();
        });
        
        eventSource.onerror = (error) => {
          clearTimeout(timeoutId);
          eventSource.close();
          this.currentEventSource = null;
          
          if (!assistantMsg.content) {
            assistantMsg.content = 'Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.';
            if (!this.messages.includes(assistantMsg)) {
              this.messages.push(assistantMsg);
            }
            this.messages[this.messages.length - 1] = assistantMsg;
            this.updateMessages();
            this.saveSession();
          }
          
          this.isStreaming = false;
          this.updateMessages();
        };
        
      } catch (error) {
        console.error('Failed to send message:', error);
        this.messages.push({
          id: this.generateId(),
          role: 'assistant',
          content: 'Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.',
          timestamp: new Date().toISOString()
        });
        this.updateMessages();
        this.saveSession();
        this.isStreaming = false;
        this.updateMessages();
      }
    }

    generateId() {
      return Math.random().toString(36).substring(2, 15);
    }

    formatTime(timestamp) {
      const date = new Date(timestamp);
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      return `${hours}:${minutes}`;
    }

    renderFooter() {
      const displayConfig = this.config.display_config || {};
      const brandingConfig = displayConfig.branding || {};
      
      if (brandingConfig.show_powered_by === false && !brandingConfig.privacy_policy_url && !brandingConfig.terms_url) {
        return '';
      }

      let brandingHTML = '';
      if (brandingConfig.show_powered_by !== false) {
        brandingHTML = `
          <div id="chatbot-branding">
            <span>Powered by</span>
            ${brandingConfig.company_logo_url ? 
              `<img src="${brandingConfig.company_logo_url}" alt="${brandingConfig.company_name || 'Company'}">` : 
              (brandingConfig.company_name ? `<strong>${brandingConfig.company_name}</strong>` : '')}
          </div>
        `;
      }

      let linksHTML = '';
      if (brandingConfig.privacy_policy_url || brandingConfig.terms_url) {
        const links = [];
        if (brandingConfig.privacy_policy_url) {
          links.push(`<a href="${brandingConfig.privacy_policy_url}" target="_blank" rel="noopener">Privacy Policy</a>`);
        }
        if (brandingConfig.terms_url) {
          links.push(`<a href="${brandingConfig.terms_url}" target="_blank" rel="noopener">Terms of Service</a>`);
        }
        linksHTML = `
          <div id="chatbot-links">
            ${links.join('<span> • </span>')}
          </div>
        `;
      }

      return `
        <div id="chatbot-footer">
          ${brandingHTML}
          ${linksHTML}
        </div>
      `;
    }

    render() {
      const displayConfig = this.config.display_config || {};
      const colors = displayConfig.colors || {};
      const headerColors = colors.header || {};
      const buttonColors = colors.button || {};
      const inputColors = colors.input || {};
      const messageColors = colors.message || {};
      const bgColors = colors.background || {};
      const position = displayConfig.position || {};
      const size = displayConfig.size || {};
      const buttonConfig = displayConfig.button || {};
      const headerConfig = displayConfig.header || {};
      const welcomeMsg = displayConfig.welcome_message || {};
      const inputConfig = displayConfig.input || {};
      
      const container = document.createElement('div');
      container.id = 'chatbot-widget-container';
      container.innerHTML = `
        <style>
          #chatbot-widget-container {
            position: fixed;
            ${position.vertical === 'top' ? 'top' : 'bottom'}: ${position.vertical === 'top' ? position.offset_y || 20 : position.offset_y || 20}px;
            ${position.horizontal === 'left' ? 'left' : 'right'}: ${position.horizontal === 'left' ? position.offset_x || 20 : position.offset_x || 20}px;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
          }
          
          #chatbot-toggle-btn {
            width: ${buttonConfig.size || 60}px;
            height: ${buttonConfig.size || 60}px;
            border-radius: 50%;
            background-color: ${buttonColors.launcher_background || this.config.primary_color || '#3b82f6'};
            color: ${buttonColors.launcher_icon || 'white'};
            border: none;
            padding: 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
          }
          
          #chatbot-toggle-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
          }
          
          #chatbot-toggle-btn svg {
            width: 28px;
            height: 28px;
            display: block;
          }
          
          #chatbot-toggle-btn svg path {
            stroke: ${buttonColors.launcher_icon || 'white'} !important;
            fill: none !important;
          }
          
          #chatbot-window {
            display: none;
            position: fixed;
            ${position.vertical === 'top' ? 'top' : 'bottom'}: ${position.vertical === 'top' ? (position.offset_y || 20) + (buttonConfig.size || 60) + 10 : (position.offset_y || 20) + (buttonConfig.size || 60) + 10}px;
            ${position.horizontal === 'left' ? 'left' : 'right'}: ${position.horizontal === 'left' ? position.offset_x || 20 : position.offset_x || 20}px;
            width: ${size.width || 400}px;
            height: ${size.height || 600}px;
            background: ${bgColors.main || 'white'};
            border-radius: 12px;
            box-shadow: 0 10px 40px ${colors.shadow || 'rgba(0,0,0,0.2)'};
            flex-direction: column;
            overflow: hidden;
          }
          
          #chatbot-window.open {
            display: flex;
          }
          
          #chatbot-header {
            background-color: ${headerColors.background || this.config.primary_color || '#3b82f6'};
            color: ${headerColors.text || 'white'};
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            ${headerColors.border ? `border-bottom: 1px solid ${headerColors.border};` : ''}
          }
          
          #chatbot-header-info {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
          }
          
          #chatbot-header-title {
            display: flex;
            flex-direction: column;
          }
          
          #chatbot-header-actions {
            display: flex;
            gap: 8px;
          }
          
          #chatbot-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: white;
            flex-shrink: 0;
          }
          
          #chatbot-new-chat-btn,
          #chatbot-close-btn {
            background: rgba(255,255,255,0.2);
            border: none;
            color: ${headerColors.icon || 'white'};
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
            transition: background 0.2s;
            flex-shrink: 0;
          }
          
          #chatbot-new-chat-btn:hover,
          #chatbot-close-btn:hover {
            background: rgba(255,255,255,0.3);
          }
          
          #chatbot-new-chat-btn svg,
          #chatbot-close-btn svg {
            width: 20px;
            height: 20px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
          }
            flex-shrink: 0;
          }
          
          #chatbot-close-btn svg,
          #chatbot-send-btn svg {
            display: block;
            pointer-events: none;
            color: inherit;
          }
          
          #chatbot-messages {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            background: ${bgColors.chat_area || '#f9fafb'};
          }
          
          .chatbot-message {
            margin-bottom: 16px;
            display: flex;
            gap: 8px;
            animation: slideUp 0.3s ease-out;
          }
          
          @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
          
          .chatbot-message.user {
            justify-content: flex-end;
          }
          
          .chatbot-message-content {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.5;
          }
          
          .chatbot-message.user .chatbot-message-content {
            background-color: ${messageColors.user_background || this.config.primary_color || '#3b82f6'};
            color: ${messageColors.user_text || 'white'};
          }
          
          .chatbot-message.assistant .chatbot-message-content {
            background: ${messageColors.bot_background || 'white'};
            color: ${messageColors.bot_text || '#1f2937'};
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          }
          
          .chatbot-message-time {
            font-size: 11px;
            margin-top: 4px;
          }
          
          .chatbot-message.user .chatbot-message-time {
            color: rgba(255, 255, 255, 0.8);
          }
          
          .chatbot-message.assistant .chatbot-message-time {
            color: rgba(0, 0, 0, 0.5);
          }
          
          #chatbot-input-container {
            padding: 16px;
            background: ${bgColors.main || 'white'};
            border-top: 1px solid ${colors.divider || '#e5e7eb'};
            display: flex;
            gap: 8px;
          }
          
          #chatbot-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid ${inputColors.border || '#d1d5db'};
            border-radius: 24px;
            outline: none;
            font-size: 14px;
            background: ${inputColors.background || 'white'};
            color: ${inputColors.text || '#1f2937'};
          }
          
          #chatbot-input::placeholder {
            color: ${inputColors.placeholder || '#9ca3af'};
          }
          
          #chatbot-input:focus {
            border-color: ${inputColors.border_focus || this.config.primary_color || '#3b82f6'};
          }
          
          #chatbot-send-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background-color: ${buttonColors.send_button || this.config.primary_color || '#3b82f6'};
            color: ${buttonColors.launcher_icon || 'white'};
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            padding: 0;
            transition: transform 0.2s, background 0.2s;
          }
          
          #chatbot-send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background-color: ${buttonColors.send_button_disabled || '#d1d5db'};
          }
          
          #chatbot-send-btn:hover:not(:disabled) {
            transform: scale(1.05);
          }
          
          #chatbot-send-btn svg {
            width: 20px;
            height: 20px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
          }
          
          .chatbot-loader {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid ${colors.divider || '#d1d5db'};
            border-top-color: ${headerColors.background || this.config.primary_color || '#3b82f6'};
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
          }
          
          /* Markdown styles */
          .chatbot-message-content code {
            background: rgba(0, 0, 0, 0.05);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
          }
          
          .chatbot-message-content pre {
            background: rgba(0, 0, 0, 0.05);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
          }
          
          .chatbot-message-content pre code {
            background: none;
            padding: 0;
          }
          
          .chatbot-message-content strong {
            font-weight: 600;
          }
          
          .chatbot-message-content em {
            font-style: italic;
          }
          
          .chatbot-message-content ul, 
          .chatbot-message-content ol {
            margin: 8px 0;
            padding-left: 24px;
          }
          
          .chatbot-message-content li {
            margin: 4px 0;
          }
          
          .chatbot-message-content a {
            color: ${headerColors.background || this.config.primary_color || '#3b82f6'};
            text-decoration: underline;
            word-break: break-word;
            overflow-wrap: break-word;
          }
          
          .chatbot-message-content a:hover {
            opacity: 0.8;
          }
          
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          
          #chatbot-footer {
            padding: 12px 16px;
            background: ${bgColors.main || 'white'};
            border-top: 1px solid ${colors.divider || '#e5e7eb'};
            font-size: 12px;
            text-align: center;
            color: #6b7280;
          }
          
          #chatbot-branding {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            margin-bottom: 8px;
          }
          
          #chatbot-branding img {
            height: 16px;
            width: auto;
          }
          
          #chatbot-links {
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
          }
          
          #chatbot-links a {
            color: ${headerColors.background || this.config.primary_color || '#3b82f6'};
            text-decoration: none;
            transition: opacity 0.2s;
          }
          
          #chatbot-links a:hover {
            opacity: 0.7;
            text-decoration: underline;
          }
        </style>
        
        <div id="chatbot-window">
          <div id="chatbot-header">
            <div id="chatbot-header-info">
              ${headerConfig.avatar_url || this.config.avatar_url ? 
                `<img id="chatbot-avatar" src="${headerConfig.avatar_url || this.config.avatar_url}" alt="Bot">` : 
                '<div id="chatbot-avatar"></div>'}
              <div id="chatbot-header-title">
                <div style="font-weight: 600;">${headerConfig.title || this.config.header_title || this.config.bot_name || 'Chat'}</div>
                <div style="font-size: 12px; opacity: 0.9;">${headerConfig.subtitle || this.config.header_subtitle || 'Online'}</div>
              </div>
            </div>
            <div id="chatbot-header-actions">
              <button id="chatbot-new-chat-btn" title="Start new conversation">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
              <button id="chatbot-close-btn" title="Close chat">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
          
          <div id="chatbot-messages"></div>
          
          <div id="chatbot-input-container">
            <input 
              id="chatbot-input" 
              type="text" 
              placeholder="${inputConfig.placeholder || this.config.placeholder_text || 'Type your message...'}"
              maxlength="${inputConfig.max_length || 1000}"
            />
            <button id="chatbot-send-btn">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
          
          ${this.renderFooter()}
        </div>
        
        <button id="chatbot-toggle-btn">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="${buttonColors.launcher_icon || 'white'}" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      `;
      
      document.body.appendChild(container);
      
      if (this.messages.length > 0) {
        this.updateMessages();
      }
    }

    attachEventListeners() {
      const toggleBtn = document.getElementById('chatbot-toggle-btn');
      const closeBtn = document.getElementById('chatbot-close-btn');
      const newChatBtn = document.getElementById('chatbot-new-chat-btn');
      const input = document.getElementById('chatbot-input');
      const sendBtn = document.getElementById('chatbot-send-btn');
      
      toggleBtn.addEventListener('click', () => this.open());
      closeBtn.addEventListener('click', () => this.close());
      newChatBtn.addEventListener('click', () => this.startNewChat());
      
      sendBtn.addEventListener('click', () => this.handleSend());
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !this.isStreaming) {
          this.handleSend();
        }
      });
    }

    async startNewChat() {
      if (this.isStreaming) {

        if (this.currentEventSource) {
          this.currentEventSource.close();
          this.currentEventSource = null;
        }
        this.isStreaming = false;
      }
      
      if (this.session?.session_token) {
        try {
          await fetch(`${this.apiUrl}/api/v1/chat/sessions/${this.session.session_token}/close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              reason: 'user_started_new_chat'
            })
          });
        } catch (error) {
          console.warn('Failed to close old session:', error);
        }
      }
      
      // Clear current session
      localStorage.removeItem(`chatbot_session_${this.botId}`);
      localStorage.removeItem(`chatbot_messages_${this.botId}`);
      
      this.session = null;
      this.messages = [];
      
      await this.createSession();
      this.updateMessages();
    }

    async open() {
      this.isOpen = true;
      const windowEl = document.getElementById('chatbot-window');
      if (windowEl) {
        windowEl.classList.add('open');
      } else {
        console.error('[Chatbot Widget] Cannot open - window element not found');
        return;
      }
      
      if (!this.session) {
        await this.createSession();
        this.updateMessages();
      }
      
      this.scrollToBottom();
    }

    close() {
      this.isOpen = false;
      document.getElementById('chatbot-window').classList.remove('open');
    }

    handleSend() {
      const input = document.getElementById('chatbot-input');
      const message = input.value.trim();
      
      if (!message || this.isStreaming) return;
      
      input.value = '';
      this.sendMessage(message);
    }

    updateMessages() {
      const container = document.getElementById('chatbot-messages');
      
      container.innerHTML = this.messages.map(msg => `
        <div class="chatbot-message ${msg.role}">
          <div class="chatbot-message-content">
            <div>${this.renderMarkdown(msg.content)}</div>
            ${this.config.display_config?.show_timestamp !== false && msg.content ? 
              `<div class="chatbot-message-time">${this.formatTime(msg.timestamp)}</div>` : ''}
          </div>
        </div>
      `).join('');
      
      if (this.isStreaming) {
        container.innerHTML += `
          <div class="chatbot-message assistant">
            <div class="chatbot-message-content">
              <div>${this.renderMarkdown(this.pendingAssistantContent) || '<div class="chatbot-loader"></div>'}</div>
            </div>
          </div>
        `;
      }
      
      this.scrollToBottom();
      
      const sendBtn = document.getElementById('chatbot-send-btn');
      sendBtn.disabled = this.isStreaming;
    }

    renderMarkdown(text) {
      if (!text) return '';
      
      let html = text.replace(/[&<>"']/g, (match) => {
        const escapeMap = {
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        };
        return escapeMap[match];
      });
      
      html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
      });
      
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      html = html.replace(/^[\-\*\+] (.+)$/gm, '<li>$1</li>');
      html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
      html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
      html = html.replace(/\n/g, '<br>');
      
      return html;
    }

    scrollToBottom() {
      const container = document.getElementById('chatbot-messages');
      container.scrollTop = container.scrollHeight;
    }
  }

  window.ChatbotWidget = {
    init: function(config) {
      if (!config.botId) {
        console.error('ChatbotWidget: botId is required');
        return;
      }
      new ChatbotWidget(config);
    }
  };

  const script = document.currentScript;
  if (script && script.hasAttribute('data-bot-id')) {
    const botId = script.getAttribute('data-bot-id');
    let apiUrl = script.getAttribute('data-api-url');
    
    if (!apiUrl && script.src) {
      try {
        const url = new URL(script.src);
        apiUrl = `${url.protocol}//${url.host}`;
      } catch (e) {
        console.error('Failed to detect API URL from script src:', e);
      }
    }
    
    window.ChatbotWidget.init({
      botId: botId,
      apiUrl: apiUrl
    });
  }
})();
