export const parsePositiveIntParam = (value: string | null): string | undefined => {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (trimmed.length === 0) return undefined;
  if (!/^\d+$/.test(trimmed)) return undefined;
  const num = Number(trimmed);
  if (!Number.isFinite(num) || num <= 0) return undefined;
  return String(num);
};
