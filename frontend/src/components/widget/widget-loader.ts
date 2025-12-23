/**
 * Widget Embed Script
 * Standalone script for embedding chatbot widget on any website
 * 
 * Usage:
 * <script src="https://your-domain.com/widget.js"></script>
 * <script>
 *   ChatbotWidget.init({
 *     botId: 'your-bot-id',
 *     apiUrl: 'https://api.your-domain.com'
 *   });
 * </script>
 */

(function() {
  'use strict';

  // Widget configuration
  interface WidgetConfig {
    botId: string;
    apiUrl?: string;
    containerId?: string;
    className?: string;
    onError?: (error: Error) => void;
  }

  // Widget instance
  let widgetInstance: { destroy: () => void; container?: HTMLElement; config?: WidgetConfig; component?: unknown } | null = null;

  // Public API
  const ChatbotWidget = {
    /**
     * Initialize the widget
     */
    init(config: WidgetConfig): void {
      if (widgetInstance) {
        console.warn('ChatbotWidget already initialized');
        return;
      }

      // Validate required config
      if (!config.botId) {
        throw new Error('botId is required');
      }

      // Set API URL in window for widget to pick up
      if (config.apiUrl) {
        window.__CHATBOT_API_URL__ = config.apiUrl;
      }

      // Create container
      const containerId = config.containerId || 'chatbot-widget-root';
      let container = document.getElementById(containerId);
      
      if (!container) {
        container = document.createElement('div');
        container.id = containerId;
        if (config.className) {
          container.className = config.className;
        }
        document.body.appendChild(container);
      }

      // Load React app
      this.loadWidget(container, config);
    },

    /**
     * Destroy the widget
     */
    destroy(): void {
      if (!widgetInstance) {
        return;
      }

      const container = document.getElementById('chatbot-widget-root');
      if (container) {
        container.remove();
      }

      widgetInstance = null;
    },

    /**
     * Load widget script and mount React component
     */
    loadWidget(container: HTMLElement, config: WidgetConfig): void {
      // This would load the bundled React app
      // For production, replace with actual bundle loading logic
      
      import('./ChatWidget').then((module) => {
        const ChatWidget = module.default;
        
        // Mount React component (pseudo-code)
        // In reality, you'd use ReactDOM.render or createRoot
        widgetInstance = {
          container,
          config,
          component: ChatWidget,
          destroy: () => {
            if (container && container.parentNode) {
              container.parentNode.removeChild(container);
            }
          }
        };
        
        console.log('ChatbotWidget initialized', config);
      }).catch((error) => {
        console.error('Failed to load ChatWidget:', error);
        if (config.onError) {
          config.onError(error);
        }
      });
    },
  };

  // Expose to window
  (window as typeof window & { ChatbotWidget: typeof ChatbotWidget }).ChatbotWidget = ChatbotWidget;

  // Auto-init if data attributes present
  document.addEventListener('DOMContentLoaded', () => {
    const scripts = document.querySelectorAll('script[data-chatbot-widget]');
    
    scripts.forEach((script) => {
      const botId = script.getAttribute('data-bot-id');
      const apiUrl = script.getAttribute('data-api-url');
      
      if (botId) {
        ChatbotWidget.init({
          botId,
          apiUrl: apiUrl || undefined,
        });
      }
    });
  });
})();
