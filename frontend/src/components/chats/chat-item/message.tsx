"use client";

import { MessageType } from "@/types/chatbot.type";
import React from "react";
import ReactMarkdown from "react-markdown";

interface MessageProps {
  content: MessageType;
}

export const Message: React.FC<MessageProps> = ({ content }) => {
  return (
    <React.Fragment>
      {/* User message (right side) */}
      {content.message && (
        <div className="bg-blue-500 text-white rounded-xl px-4 py-1 w-fit my-1 float-right">
          {content.message}
        </div>
      )}

      {/* AI response (left side) */}
      {content.response && (
        <div className="bg-blue-50 rounded-xl px-4 py-1 w-fit float-left my-1">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {content.response}
          </ReactMarkdown>
        </div>
      )}
    </React.Fragment>
  );
};
