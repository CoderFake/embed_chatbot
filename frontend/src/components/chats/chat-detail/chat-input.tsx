import { useEffect, useRef } from "react";
import { Control, Controller } from "react-hook-form";

interface ChatInputProps {
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  control: Control<any>;
  onEnterPress: (e: React.FormEvent) => void;
}

export default function ChatInput({
  name,
  control,
  onEnterPress,
}: ChatInputProps) {
  const textRef = useRef<HTMLInputElement | null>(null);
  
  useEffect(() => {
    textRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      onEnterPress(e);
    }
  };

  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <input
          {...field}
          ref={(el) => {
            textRef.current = el;
            field.ref(el);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask me anything..."
          className="flex-1 bg-transparent text-[#425b76] focus:outline-none line-clamp-1 text-base"
        />
      )}
    />
  );
}
