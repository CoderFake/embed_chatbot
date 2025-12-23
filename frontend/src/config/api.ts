/**
 * API Configuration
 * Centralized configuration for API endpoints and behaviors
 */

/**
 * Public endpoints that don't require authentication
 * These endpoints will:
 * - Not have Authorization header attached
 * - Not trigger token refresh on 401 errors
 */
export const PUBLIC_ENDPOINTS = [
  '/auth/login',
  '/auth/refresh',
  '/admin/invites/confirm',
  '/auth/forgot-password',
  '/auth/reset-password',
] as const;

/**
 * Check if a URL matches any public endpoint
 */
export function isPublicEndpoint(url: string | undefined): boolean {
  if (!url) return false;
  return PUBLIC_ENDPOINTS.some(endpoint => url.includes(endpoint));
}

/**
 * API base URL from environment
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

