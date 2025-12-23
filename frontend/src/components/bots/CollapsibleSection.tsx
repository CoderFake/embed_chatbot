"use client";

import { ChevronDown, ChevronRight } from "lucide-react";

interface CollapsibleSectionProps {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

export const CollapsibleSection = ({ title, isOpen, onToggle, children }: CollapsibleSectionProps) => {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {isOpen ? <ChevronDown className="w-5 h-5 text-gray-600" /> : <ChevronRight className="w-5 h-5 text-gray-600" />}
      </button>
      {isOpen && <div className="p-4 bg-white">{children}</div>}
    </div>
  );
};

