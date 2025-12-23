"use client";

import React, { useEffect, useState } from "react";

interface AnimationLoadingMessageProps {
  time: number;
  loadingText?: string;
  loading: boolean;
}

const AnimationLoadingMessage = ({
  time = 5000,
  loadingText = "loading...",
  loading = false,
}: AnimationLoadingMessageProps) => {
  const [showLoadingText, setShowLoadingText] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (loading) {
      timer = setTimeout(() => {
        setShowLoadingText(true);
      }, time);
    }

    return () => clearTimeout(timer);
  }, [loading, time]);
  return (
    <div className="max-w-3xl mx-auto py-6 px-4 flex items-center gap-x-3">
      <span className="relative flex size-3">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
        <span className="relative inline-flex size-3 rounded-full bg-sky-500"></span>
      </span>

      <div
        className={`loading-text opacity-0 transition-all
          ${showLoadingText && "opacity-100"}`}
      >
        <span className="text-14 font-500">{loadingText}</span>
      </div>
    </div>
  );
};

export default AnimationLoadingMessage;
