export const modelNameRegex = /^[a-zA-Z0-9_-]+$/;
export const projectNameRegex = /^[a-zA-Z0-9_-]+$/;

export function cn(...classes: string[]) {
  return classes.filter(Boolean).join(' ');
}