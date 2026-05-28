/**
 * Tiny utility module — currently only `cn` for Tailwind class merging.
 *
 * @module utils
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge a list of Tailwind class fragments, deduping conflicting utilities
 * via `tailwind-merge`. Use whenever a component combines a default
 * className with caller-provided overrides.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
