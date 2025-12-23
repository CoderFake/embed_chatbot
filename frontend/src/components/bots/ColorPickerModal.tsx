"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { X, Pipette, Copy, Check } from "lucide-react";
interface ColorPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  value: string;
  onChange: (color: string) => void;
  label: string;
}

export const ColorPickerModal = ({ isOpen, onClose, value, onChange, label }: ColorPickerModalProps) => {
  const [tempColor, setTempColor] = useState(value);
  const [hue, setHue] = useState(0);
  const [saturation, setSaturation] = useState(100);
  const [brightness, setBrightness] = useState(100);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedPosition, setSelectedPosition] = useState({ x: 0, y: 0 });
  const [copied, setCopied] = useState(false);

  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  };

  const rgbToHsb = (r: number, g: number, b: number) => {
    r /= 255;
    g /= 255;
    b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    
    let h = 0;
    if (delta !== 0) {
      if (max === r) h = ((g - b) / delta) % 6;
      else if (max === g) h = (b - r) / delta + 2;
      else h = (r - g) / delta + 4;
      h = Math.round(h * 60);
      if (h < 0) h += 360;
    }
    
    const s = max === 0 ? 0 : Math.round((delta / max) * 100);
    const bVal = Math.round(max * 100);
    
    return { h, s, b: bVal };
  };

  const hsbToRgb = (h: number, s: number, b: number) => {
    s = s / 100;
    b = b / 100;
    const k = (n: number) => (n + h / 60) % 6;
    const f = (n: number) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
    return {
      r: Math.round(255 * f(5)),
      g: Math.round(255 * f(3)),
      b: Math.round(255 * f(1))
    };
  };

  const rgbToHex = (r: number, g: number, b: number) => {
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  };

  const updateColor = (newHue: number, newSat: number, newBright: number) => {
    setHue(newHue);
    setSaturation(newSat);
    setBrightness(newBright);
    const rgb = hsbToRgb(newHue, newSat, newBright);
    const hex = rgbToHex(rgb.r, rgb.g, rgb.b);
    setTempColor(hex);
  };

  const drawColorWheel = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const size = 280;
    const centerX = size / 2;
    const centerY = size / 2;
    const radius = size / 2 - 10;

    canvas.width = size;
    canvas.height = size;

    // Draw color wheel
    for (let angle = 0; angle < 360; angle++) {
      const startAngle = (angle - 90) * Math.PI / 180;
      const endAngle = (angle + 1 - 90) * Math.PI / 180;

      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, startAngle, endAngle);
      ctx.closePath();

      const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius);
      gradient.addColorStop(0, `hsl(${angle}, 0%, ${brightness}%)`);
      gradient.addColorStop(1, `hsl(${angle}, 100%, ${brightness / 2}%)`);
      
      ctx.fillStyle = gradient;
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(centerX, centerY, 20, 0, 2 * Math.PI);
    ctx.fillStyle = '#fff';
    ctx.fill();
  }, [brightness]);

  useEffect(() => {
    if (isOpen) {
      setTempColor(value);
      const rgb = hexToRgb(value);
      if (rgb) {
        const hsb = rgbToHsb(rgb.r, rgb.g, rgb.b);
        setHue(hsb.h);
        setSaturation(hsb.s);
        setBrightness(hsb.b);
      }

      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }
    
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [isOpen, value]);

  useEffect(() => {
    if (isOpen && canvasRef.current) {
      drawColorWheel();
    }
  }, [isOpen, drawColorWheel]);

  const handleWheelClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    
    const dx = x - centerX;
    const dy = y - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const radius = canvas.width / 2 - 10;
    
    if (distance > 20 && distance < radius) {
      const angle = Math.atan2(dy, dx) * 180 / Math.PI + 90;
      const newHue = (angle + 360) % 360;
      const newSat = Math.min((distance / radius) * 100, 100);
      
      setSelectedPosition({ x, y });
      updateColor(newHue, newSat, brightness);
    }
  };

  const handleSave = () => {
    onChange(tempColor);
    // Delay close to prevent scroll
    setTimeout(() => {
      onClose();
    }, 0);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(tempColor);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleEyeDropper = async () => {
    if (!('EyeDropper' in window)) {
      alert('EyeDropper API is not supported in this browser. Please use Chrome 95+ or Edge 95+');
      return;
    }

    try {
      // @ts-expect-error - EyeDropper API is experimental
      const eyeDropper = new window.EyeDropper();
      const result = await eyeDropper.open();
      
      if (result && result.sRGBHex) {
        const hex = result.sRGBHex;
        setTempColor(hex);
        const rgb = hexToRgb(hex);
        if (rgb) {
          const hsb = rgbToHsb(rgb.r, rgb.g, rgb.b);
          setHue(hsb.h);
          setSaturation(hsb.s);
          setBrightness(hsb.b);
        }
      }
    } catch {
      console.log('EyeDropper cancelled');
    }
  };

  const handleHexInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const hex = e.target.value;
    setTempColor(hex);
    const rgb = hexToRgb(hex);
    if (rgb) {
      const hsb = rgbToHsb(rgb.r, rgb.g, rgb.b);
      setHue(hsb.h);
      setSaturation(hsb.s);
      setBrightness(hsb.b);
    }
  };

  const presetColors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DFE6E9', '#74B9FF', '#A29BFE', '#FD79A8', '#FDCB6E',
    '#E17055', '#00B894', '#00CEC9', '#0984E3', '#6C5CE7',
    '#2D3436', '#636E72', '#B2BEC3', '#FFFFFF', '#000000',
  ];

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-2xl p-6 w-[400px] max-h-[90vh] overflow-y-auto border-2 border-gray-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{label}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Color Wheel */}
        <div className="mb-6 flex justify-center">
          <div className="relative">
            <canvas
              ref={canvasRef}
              onClick={handleWheelClick}
              className="cursor-crosshair rounded-full"
              style={{ width: 280, height: 280 }}
            />
            {selectedPosition.x > 0 && (
              <div
                className="absolute w-6 h-6 border-3 border-white rounded-full pointer-events-none"
                style={{
                  left: selectedPosition.x - 12,
                  top: selectedPosition.y - 12,
                  boxShadow: '0 0 0 1px rgba(0,0,0,0.3)',
                }}
              />
            )}
          </div>
        </div>

        {/* Brightness Slider */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 block mb-2 flex items-center justify-between">
            <span>Brightness</span>
            <span className="text-gray-500">{brightness}%</span>
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={brightness}
            onChange={(e) => updateColor(hue, saturation, parseInt(e.target.value))}
            className="w-full h-8 appearance-none bg-transparent cursor-pointer"
            style={{
              background: `linear-gradient(to right, #000, ${(() => {
                const rgb = hsbToRgb(hue, saturation, 100);
                return rgbToHex(rgb.r, rgb.g, rgb.b);
              })()})`,
              borderRadius: '4px'
            }}
          />
        </div>

        {/* Color Preview */}
        <div className="mb-4 flex gap-3 items-center">
          <div 
            className="flex-1 h-12 rounded-lg border-2 border-gray-200"
            style={{ backgroundColor: tempColor }}
          />
          <button
            type="button"
            onClick={handleEyeDropper}
            className="p-3 hover:bg-gray-100 rounded-lg border border-gray-300 transition-colors"
            title="Pick color from screen"
          >
            <Pipette className="w-5 h-5" />
          </button>
        </div>

        {/* Hex Input */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 block mb-2">
            Hex Code
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={tempColor}
              onChange={handleHexInput}
              className="input-field font-mono flex-1"
              placeholder="#000000"
            />
            <button
              type="button"
              onClick={handleCopy}
              className="px-4 py-2 hover:bg-gray-100 rounded-lg border border-gray-300 flex items-center gap-2 transition-colors"
              title="Copy to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-600">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span className="text-sm">Copy</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Preset Colors */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 block mb-2">
            Preset Colors
          </label>
          <div className="grid grid-cols-10 gap-2">
            {presetColors.map((color) => (
              <button
                key={color}
                onClick={() => {
                  setTempColor(color);
                  const rgb = hexToRgb(color);
                  if (rgb) {
                    const hsb = rgbToHsb(rgb.r, rgb.g, rgb.b);
                    setHue(hsb.h);
                    setSaturation(hsb.s);
                    setBrightness(hsb.b);
                  }
                }}
                className="w-8 h-8 rounded border-2 hover:scale-110 transition-transform"
                style={{ 
                  backgroundColor: color,
                  borderColor: tempColor === color ? '#000' : '#ddd'
                }}
                title={color}
              />
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button onClick={onClose} className="btn-outline flex-1">
            Cancel
          </button>
          <button onClick={handleSave} className="btn-primary flex-1">
            Apply
          </button>
        </div>
      </div>
    </div>
  );
};

