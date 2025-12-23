"use client";

import React, { createContext, useContext, useState } from "react";

const ChatContext = createContext<{
  show: boolean;
  setShow: (show: boolean) => void;
  idDetail: string;
  setIdDetail: (id: string) => void;
  showDetail: boolean;
  setShowDetail: (show: boolean) => void;
}>({
  show: true,
  setShow: () => {},
  idDetail: "",
  setIdDetail: () => {},
  showDetail: false,
  setShowDetail: () => {},
});

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [show, setShow] = useState<boolean>(true);
  const [idDetail, setIdDetail] = useState<string>("");
  const [showDetail, setShowDetail] = useState<boolean>(false);

  return (
    <ChatContext.Provider
      value={{
        show,
        setShow,
        idDetail,
        setIdDetail,
        showDetail,
        setShowDetail,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};
