/**
 * Global Configuration
 * Provides API URL configuration with browser and server-side support
 */

interface GlobalConfig {
  apiUrl: string;
}

/**
 * Get API URL from multiple sources (priority order):
 * 1. Window injection: window.__CHATBOT_API_URL__
 * 2. Environment variable: NEXT_PUBLIC_API_URL
 * 3. Default: http://localhost:18000
 */
function getApiUrl(): string {
  // Browser environment - check window injection first
  if (typeof window !== 'undefined') {
    const windowConfig = window.__CHATBOT_API_URL__;
    if (windowConfig) {
      return windowConfig;
    }
  }
  
  // Environment variable (works in both browser and server)
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // Default fallback
  return 'http://localhost:18000';
}

/**
 * Global configuration object
 * Access via: import { globalConfig } from '@/config/global'
 */
export const globalConfig: GlobalConfig = {
  apiUrl: getApiUrl(),
};

/**
 * Update API URL at runtime (useful for dynamic configuration)
 * @param url New API URL
 */
export function setApiUrl(url: string): void {
  (globalConfig as { apiUrl: string }).apiUrl = url;

  // Also update window injection if in browser
  if (typeof window !== 'undefined') {
    window.__CHATBOT_API_URL__ = url;
  }
}

/**
 * Type declaration for window injection
 * Add this to your global.d.ts if needed
 */
declare global {
  interface Window {
    __CHATBOT_API_URL__?: string;
  }
}
