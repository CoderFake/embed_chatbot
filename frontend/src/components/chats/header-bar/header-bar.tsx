"use client";

import React from "react";
import {
  ChevronLeft,
  Maximize2,
  MessageSquarePlus,
  Minimize2,
  X,
} from "lucide-react";
import { useChat } from "@/contexts/chat-context";
import Image from "next/image";

interface HeaderBarProps {
  title: string;
}
export default function HeaderBar({ title }: HeaderBarProps) {
  const [isMinimized, setIsMinimized] = React.useState(false);
  const { setShow, showDetail, setShowDetail, setIdDetail } = useChat();

  const toggleMinimize = () => {
    setIsMinimized(!isMinimized);
  };
  return (
    <div className="w-full flex items-center justify-between float-none overflow-hidden h-[50px] text-lg font-bold py-2 px-4 bg-blue-900 text-white rounded-t-lg flex-shrink">
      {!showDetail ? (
        <>
          <div className="overflow-hidden text-lg flex-1">{title}</div>
          <div className="flex items-center gap-2">
            <button className="cursor-pointer flex items-center justify-center p-1 transition-all duration-200 flex-shrink-0">
              <MessageSquarePlus />
            </button>
            <button
              onClick={toggleMinimize}
              className="cursor-pointer flex items-center justify-center p-1 transition-all duration-200 flex-shrink-0"
            >
              {isMinimized ? <Maximize2 /> : <Minimize2 />}
            </button>
            <button
              className="cursor-pointer flex items-center justify-center p-1 transition-all duration-200 flex-shrink-0"
              onClick={() => setShow(false)}
            >
              <X />
            </button>
          </div>
        </>
      ) : (
        <div className="w-full flex items-center justify-start gap-2">
          <button
            className="cursor-pointer flex items-center justify-center transition-all duration-200 flex-shrink-0"
            onClick={() => {
              setShowDetail(false);
              setIdDetail("");
            }}
          >
            <ChevronLeft />
          </button>
          <div className="overflow-hidden text-lg flex-1 flex items-center gap-2 justify-start">
            <div className="flex items-center justify-center rounded-full aspect-square h-8 flex-shrink-0 relative after:content-[''] after:absolute after:right-0 after:bottom-[1px] after:bg-[#00bda5] after:aspect-square after:h-3 after:border-2 after:border-white after:outline-0 after:rounded-full">
              <Image
                src={
                  "https://cdn2.hubspot.net/hub/22368174/hubfs/logo-1.jpg?width=108&height=108"
                }
                alt="logo"
                unoptimized
                width={32}
                height={32}
                className="w-full h-full object-cover rounded-full"
              />
            </div>
            <div className="flex-1 line-clamp-1 text-white">
              Newwave Solutions
            </div>
          </div>
          <button
            className="cursor-pointer flex items-center justify-center p-1 transition-all duration-200 flex-shrink-0"
            onClick={() => setShow(false)}
          >
            <X />
          </button>
        </div>
      )}
    </div>
  );
}
