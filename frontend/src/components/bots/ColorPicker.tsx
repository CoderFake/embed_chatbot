"use client";

import { useState } from "react";
import { ColorPickerModal } from "./ColorPickerModal";

interface ColorPickerProps {
  label: string;
  value: string;
  defaultValue: string;
  onChange: (color: string) => void;
}

export const ColorPicker = ({ label, value, defaultValue, onChange }: ColorPickerProps) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <div className="flex flex-col items-center gap-1 w-[60px]">
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="rounded-full border-2 border-gray-200 p-[2px] hover:border-gray-400 transition-colors"
        >
          <div
            className="w-9 h-9 rounded-full cursor-pointer"
            style={{ backgroundColor: value || defaultValue }}
          />
        </button>
        <span className="text-[10px] text-gray-600 text-center leading-tight w-full">{label}</span>
      </div>

      <ColorPickerModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        value={value || defaultValue}
        onChange={onChange}
        label={label}
      />
    </>
  );
};

