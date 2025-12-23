import { useEffect, useState } from "react";
import { apiClient } from "@/lib/auth-api";

export interface CurrentUser {
  user_id: string;
  email: string;
  role: string;
  full_name: string | null;
}

const CACHE_KEY = "current_user_cache";
const CACHE_DURATION = 5 * 60 * 1000;

let globalUserCache: { user: CurrentUser; timestamp: number } | null = null;
let fetchPromise: Promise<CurrentUser> | null = null;

export function useCurrentUser() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  const fetchCurrentUser = async () => {
    try {
      setLoading(true);

      if (globalUserCache && Date.now() - globalUserCache.timestamp < CACHE_DURATION) {
        setUser(globalUserCache.user);
        setError(null);
        setLoading(false);
        return;
      }

      if (fetchPromise) {
        const cachedUser = await fetchPromise;
        setUser(cachedUser);
        setError(null);
        setLoading(false);
        return;
      }

      fetchPromise = (async () => {
        const response = await apiClient.get<CurrentUser>("/auth/me");
        const userData = response.data;

        globalUserCache = {
          user: userData,
          timestamp: Date.now(),
        };

        if (typeof window !== 'undefined') {
          localStorage.setItem(CACHE_KEY, JSON.stringify(globalUserCache));
        }

        return userData;
      })();

      const userData = await fetchPromise;
      setUser(userData);
      setError(null);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch user";
      setError(errorMessage);
      console.error("Failed to fetch current user:", err);

      if (typeof window !== 'undefined') {
        const cached = localStorage.getItem(CACHE_KEY);
        if (cached) {
          try {
            const parsedCache = JSON.parse(cached);
            if (Date.now() - parsedCache.timestamp < CACHE_DURATION) {
              setUser(parsedCache.user);
              setError(null);
            }
          } catch {
            localStorage.removeItem(CACHE_KEY);
          }
        }
      }
    } finally {
      setLoading(false);
      fetchPromise = null;
    }
  };

  const isRoot = () => user?.role === "root";
  const isAdmin = () => user?.role === "admin" || user?.role === "root";
  const isMember = () => user?.role === "member";

  return { user, loading, error, isRoot, isAdmin, isMember, refetch: fetchCurrentUser };
}

