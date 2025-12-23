"use client";

import React from "react";
import { ChatbotPropsType } from "@/types/chatbot.type";
import HeaderBar from "./header-bar/header-bar";
import { useChat } from "@/contexts/chat-context";
import ChatContent from "./chat-content/chat-content";

interface MessageProps {
  content: ChatbotPropsType;
}

export default function ChatBot({ content }: MessageProps) {
  const { show } = useChat();
  const verticalPosition = content.display_config.position?.vertical;
  const horizontalPosition = content.display_config.position?.horizontal;
  const offset_x = content.display_config.position?.offset_x;
  const offset_y = content.display_config.position?.offset_y;
  return (
    <div
      className="bg-white w-[90%] h-[80vh] max-w-[413px] max-h-[700px] rounded-lg shadow-lg flex flex-col z-[2025] overflow-hidden"
      style={{
        position: "fixed",
        bottom: verticalPosition === "bottom" ? offset_y : "auto",
        top: verticalPosition === "top" ? offset_y : "auto",
        right: horizontalPosition === "right" ? offset_x : "auto",
        left: horizontalPosition === "left" ? offset_x : "auto",
        transformOrigin: "100% 100%",
        transition:
          "opacity 0.25s,scale 0.25s,overlay 0.25s allow-discrete,display 0.25s allow-discrete",
        opacity: show ? 1 : 0,
        scale: show ? 1 : 0,
      }}
    >
      <HeaderBar
        title={content.display_config.header.title || "Default Title"}
      />
      <ChatContent />
    </div>
  );
}
