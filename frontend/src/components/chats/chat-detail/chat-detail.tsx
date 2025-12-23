"use client";

import React, { useEffect, useRef, useState } from "react";
import ChatInput from "./chat-input";
import { useForm } from "react-hook-form";
import { MessageType } from "@/types/chatbot.type";
import { Loader2, Send, AlignJustify } from "lucide-react";
import { Message } from "../chat-item/message";

interface ChatDetailProps {
  id?: string;
}
interface FormInputs {
  message: string;
}

export default function ChatDetail({ id }: ChatDetailProps) {
  console.log(id);

  const [loadingResponseMessage, setLoadingResponseMessage] = useState(false);
  const [messages, setMessages] = useState<MessageType[]>([]);

  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const userMessageRef = useRef<HTMLDivElement>(null);
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const { control, handleSubmit, setValue, setFocus } = useForm<FormInputs>({
    defaultValues: { message: "" },
  });

  useEffect(() => {
    if (!Boolean(id)) return;
    // Simulate fetching initial messages
    const initialMessages: MessageType[] = [
      {
        message_id: "1",
        message: "Hello! How can I assist you today?",
        response: "Sure! Here are some questions you can ask me:",
        metadata: {
          follow_up_questions: [
            "What services do you offer?",
            "How can I contact support?",
          ],
        },
      },
    ];
    setMessages(initialMessages);
  }, [id]);

  useEffect(() => {
    setFocus("message");
  }, [setFocus]);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const onSubmit = async (data: FormInputs) => {
    const message = data.message.trim();
    if (!message || loadingResponseMessage) return;
    setValue("message", "");
    try {
      setLoadingResponseMessage(true);
      setTimeout(() => {
        setLoadingResponseMessage(false);
      }, 2000);
      console.log(data.message);
    } catch (error) {
      console.error("❌ Error sending message:", error);
      setLoadingResponseMessage(false);
    }
  };

  return (
    <div className="w-full flex flex-col flex-1 min-h-0 overflow-hidden">
      <div
        className="flex-1 p-2 overflow-y-auto bg-amber-100 min-h-0"
        ref={messagesContainerRef}
      >
        {messages.length !== 0 ? (
          messages.map((msg, index) => (
            <div
              key={msg.message_id}
              className="mb-4 w-full h-full"
              ref={index === messages.length - 1 ? userMessageRef : null}
            >
              <Message content={msg} />
            </div>
          ))
        ) : (
          <div className="text-center text-gray-500">
            No messages yet. Start the conversation!
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>
      <div className="w-full flex items-center justify-start gap-1 border-0 border-t border-t-[#99acc2] p-2 bg-white flex-shrink-0">
        <div className="flex items-center justify-center text-[#cbd6e2] hover:text-white hover:bg-blue-100 cursor-pointer p-2 rounded-full">
          <AlignJustify />
        </div>
        <form
          className="flex items-center justify-start gap-2 max-w-full w-full pl-2 relative"
          onSubmit={handleSubmit(onSubmit)}
        >
          <ChatInput
            name="message"
            control={control}
            onEnterPress={handleSubmit(onSubmit)}
          />
          <div
            className="flex items-center justify-center text-[#cbd6e2] hover:text-white hover:bg-blue-100 cursor-pointer p-2 rounded-full"
            onClick={handleSubmit(onSubmit)}
          >
            {loadingResponseMessage ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
