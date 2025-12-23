"use client";

import { useEffect, useState } from "react";
import { Logo } from "./Logo";

/**
 * ClientOnly wrapper component
 * 
 * Prevents hydration errors by only rendering children after client-side mount.
 * Shows a beautiful loading screen during initialization.
 */
export function ClientOnly({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Minimum delay to ensure smooth loading and prevent language flash
    const timer = setTimeout(() => {
      setMounted(true);
    }, 800);

    return () => clearTimeout(timer);
  }, []);

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-gray-100 to-gray-50">
        <div className="text-center">
          {/* Logo with fade-in animation */}
          <div className="mb-8 flex justify-center opacity-0 animate-[fadeIn_0.5s_ease-in_forwards]">
            <div className="transform hover:scale-105 transition-transform scale-150">
              <Logo variant="full" />
            </div>
          </div>

          {/* Loading Spinner */}
          <div className="flex justify-center mb-6 opacity-0 animate-[fadeIn_0.5s_ease-in_0.2s_forwards]">
            <div className="relative">
              {/* Background circle */}
              <div className="w-16 h-16 border-4 border-gray-200 rounded-full"></div>
              {/* Spinning circle */}
              <div className="w-16 h-16 border-4 border-[var(--color-primary)] rounded-full absolute top-0 left-0 animate-spin border-t-transparent"></div>
            </div>
          </div>

          {/* Loading Text with pulse */}
          <p className="text-gray-600 font-medium opacity-0 animate-[fadeIn_0.5s_ease-in_0.4s_forwards]">
            <span className="inline-block animate-pulse">Loading</span>
            <span className="inline-block animate-[pulse_1s_ease-in-out_0.2s_infinite]">.</span>
            <span className="inline-block animate-[pulse_1s_ease-in-out_0.4s_infinite]">.</span>
            <span className="inline-block animate-[pulse_1s_ease-in-out_0.6s_infinite]">.</span>
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
