"use client";

import React from "react";
import ChatItem from "../chat-item/chat-item";
import { useChat } from "@/contexts/chat-context";

export default function ChatHistory() {
  const { setShowDetail, setIdDetail } = useChat();

  return (
    <div className="w-full flex-1 overflow-y-auto">
      <ChatItem
        title="Chat Item 1"
        description="This is a chat item description."
        time="1 hr. ago"
        onClick={() => {
          setShowDetail(true);
          setIdDetail("chat-item-1");
        }}
      />
      <ChatItem
        title="Chat Item 2"
        description="This is a chat item description."
        time="3 hrs. ago"
        onClick={() => {
          setShowDetail(true);
          setIdDetail("chat-item-2");
        }}
      />
      <ChatItem
        title="Chat Item 3"
        description="This is a chat item description."
        time="2 hrs. ago"
        onClick={() => {
          setShowDetail(true);
          setIdDetail("chat-item-3");
        }}
      />
    </div>
  );
}
