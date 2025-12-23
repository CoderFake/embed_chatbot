"use client";

import Image from "next/image";
import React from "react";

interface ChatItemProps {
  title: string;
  description?: string;
  time: string;
  onClick: () => void;
}
export default function ChatItem({
  title,
  description,
  time,
  onClick,
}: ChatItemProps) {
  return (
    <div
      className="w-full text-sm no-underline transition-all duration-200 hover:bg-gray-100 flex items-center justify-start border-0 p-0 h-20 border-b border-blue-100 cursor-pointer"
      onClick={onClick}
    >
      <div className="text-left w-full flex items-center p-4 h-full gap-2">
        <div className="flex items-center justify-center rounded-full aspect-square h-full overflow-hidden flex-shrink-0">
          <Image
            src={
              "https://cdn2.hubspot.net/hub/22368174/hubfs/logo-1.jpg?width=108&height=108"
            }
            alt="logo"
            unoptimized
            width={40}
            height={40}
            className="w-full h-full object-cover"
          />
        </div>
        <div className="flex flex-col items-start gap-2 flex-1">
          <div className="flex items-center font-medium text-[#33475b] w-full gap-1">
            <div className="text-sm flex-1 text-nowrap">{title}</div>
            {time && (
              <div className="flex flex-col items-start gap-2 w-fit flex-shrink-0">
                <time
                  dateTime="2023-03-15T12:00:00Z"
                  className="text-xs font-normal max-w-12 line-clamp-1"
                >
                  {time}
                </time>
              </div>
            )}
          </div>
          {description && (
            <div className="text-xs text-[#33475b] w-full line-clamp-1">
              {description}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
