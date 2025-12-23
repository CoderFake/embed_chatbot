"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiClient } from "@/lib/auth-api";

interface AuthGuardProps {
  children: React.ReactNode;
}

const PUBLIC_ROUTES = ["/login", "/change-password", "/accept-invite"];

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, clearAuth } = useAuth();
  const [isVerifying, setIsVerifying] = useState(true);

  useEffect(() => {
    const verifyAuth = async () => {
      const isPublicRoute = PUBLIC_ROUTES.some((route) =>
        pathname?.startsWith(route)
      );

      if (isPublicRoute) {
        if (isAuthenticated) {
          router.push("/dashboard");
        }
        setIsVerifying(false);
        return;
      }

      const storedAccessToken = localStorage.getItem("access_token");
      const storedRefreshToken = localStorage.getItem("refresh_token");

      if (!storedAccessToken || !storedRefreshToken) {
        clearAuth();
        router.push("/login");
        setIsVerifying(false);
        return;
      }

      try {
        await apiClient.get("/auth/me");
        setIsVerifying(false);
      } catch (error) {
        console.error("Auth verification failed:", error);
        clearAuth();
        router.push("/login");
        setIsVerifying(false);
      }
    };

    verifyAuth();
  }, [pathname, router, isAuthenticated, clearAuth]);

  if (isVerifying) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-primary)]"></div>
      </div>
    );
  }

  return <>{children}</>;
}

