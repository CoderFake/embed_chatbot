/**
 * Auth utility functions for token management
 */

import { getCookie } from './cookies';

/**
 * Get access token from localStorage or cookies
 */
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token') || getCookie('access_token');
}

/**
 * Get refresh token from localStorage or cookies
 */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token') || getCookie('refresh_token');
}

/**
 * Set tokens in both localStorage and cookies
 */
export function setTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === 'undefined') return;
  
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
  
  document.cookie = `access_token=${accessToken}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  document.cookie = `refresh_token=${refreshToken}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
}

/**
 * Clear all tokens from localStorage and cookies
 */
export function clearTokens(): void {
  if (typeof window === 'undefined') return;
  
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  
  document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  document.cookie = 'refresh_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
}

