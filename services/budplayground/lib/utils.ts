import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import chroma from "chroma-js";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getChromeColor(color: string) {
  try {
    return chroma(color).alpha(0.1).css();
  } catch (error) {
    return "transparent";
  }
}
