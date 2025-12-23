"use client";

import React from "react";
import { useChat } from "@/contexts/chat-context";
import ChatDetail from "../chat-detail/chat-detail";
import ChatHistory from "../chat-history/chat-history";

export default function ChatContent() {
  const { showDetail, idDetail } = useChat();

  return (
    <div className="w-full flex flex-1 min-h-0 overflow-hidden flex-col">
      {showDetail ? <ChatDetail id={idDetail} /> : <ChatHistory />}
    </div>
  );
}
