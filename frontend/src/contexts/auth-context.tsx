"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { authAPI } from "@/lib/auth-api";

interface AuthContextType {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  setTokens: () => {},
  clearAuth: () => {},
  logout: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // Load tokens from localStorage on mount
    const storedAccessToken = localStorage.getItem("access_token");
    const storedRefreshToken = localStorage.getItem("refresh_token");
    
    if (storedAccessToken && storedRefreshToken) {
      setAccessToken(storedAccessToken);
      setRefreshToken(storedRefreshToken);
      setIsAuthenticated(true);
    }
  }, []);

  const setTokens = (newAccessToken: string, newRefreshToken: string) => {
    localStorage.setItem("access_token", newAccessToken);
    localStorage.setItem("refresh_token", newRefreshToken);
    setAccessToken(newAccessToken);
    setRefreshToken(newRefreshToken);
    setIsAuthenticated(true);
  };

  const clearAuth = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    setAccessToken(null);
    setRefreshToken(null);
    setIsAuthenticated(false);
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      clearAuth();
    }
  };

  return (
    <AuthContext.Provider 
      value={{ 
        accessToken, 
        refreshToken, 
        isAuthenticated, 
        setTokens, 
        clearAuth,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
