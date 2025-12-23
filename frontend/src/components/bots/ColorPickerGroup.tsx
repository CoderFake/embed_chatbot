"use client";

import { ColorPicker } from "./ColorPicker";

interface ColorItem {
  key: string;
  label: string;
  default: string;
}

interface ColorPickerGroupProps {
  title: string;
  items: ColorItem[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export const ColorPickerGroup = ({ title, items, values, onChange }: ColorPickerGroupProps) => {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-700 mb-3">{title}</h3>
      <div className="flex gap-3 flex-wrap">
        {items.map((item) => (
          <ColorPicker
            key={item.key}
            label={item.label}
            value={values[item.key]}
            defaultValue={item.default}
            onChange={(color) => onChange(item.key, color)}
          />
        ))}
      </div>
    </div>
  );
};

