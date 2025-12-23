import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx
 * Usage: cn('px-2 py-1', condition && 'bg-blue-500', { 'font-bold': isActive })
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
