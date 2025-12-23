"use client";

import { useState, useRef } from "react";
import { Upload, X } from "lucide-react";

interface ImageUploadProps {
  label: string;
  value?: string;
  onChange: (file: File | null, previewUrl?: string) => void;
  accept?: string;
}

export const ImageUpload = ({ label, value, onChange, accept = "image/*" }: ImageUploadProps) => {
  const [preview, setPreview] = useState(value || "");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      console.error("File size exceeds 5MB");
      return;
    }

    // Validate file type
    if (!file.type.startsWith("image/")) {
      console.error("File must be an image");
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setPreview(previewUrl);
    
    // Pass file to parent
    onChange(file, previewUrl);
  };

  const handleRemove = () => {
    setPreview("");
    onChange(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      
      {preview ? (
        <div className="relative inline-block">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt={label}
            className="w-24 h-24 object-cover rounded-lg border-2 border-gray-200"
          />
          <button
            type="button"
            onClick={handleRemove}
            className="absolute -top-2 -right-2 p-1 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            onChange={handleFileSelect}
            className="hidden"
            id={`upload-${label}`}
          />
          <label
            htmlFor={`upload-${label}`}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
          >
            <Upload className="w-4 h-4" />
            <span className="text-sm">Choose Image</span>
          </label>
        </div>
      )}
      
      <p className="text-xs text-gray-500">Max 5MB, JPG/PNG/WebP</p>
    </div>
  );
};

