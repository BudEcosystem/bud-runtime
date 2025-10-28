const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const candidateEnvValues = () => [
  process.env.NEXT_PUBLIC_BUD_GATEWAY_BASE_URL,
  process.env.BUD_GATEWAY_BASE_URL,
  process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL,
  process.env.NEXT_PUBLIC_TEMP_API_BASE_URL,
  process.env.NEXT_PUBLIC_BASE_URL,
];

const resolveBaseHost = (preferred?: string | null): string => {
  const candidates = [preferred, ...candidateEnvValues(), 'https://gateway.dev.bud.studio'];

  for (const candidate of candidates) {
    if (candidate && typeof candidate === 'string') {
      const trimmed = candidate.trim();
      if (trimmed.length > 0) {
        return trimTrailingSlash(trimmed);
      }
    }
  }

  return 'https://gateway.dev.bud.studio';
};

export const resolveChatBaseUrl = (preferred?: string | null): string => {
  const host = resolveBaseHost(preferred);
  if (/\/openai\/v1$/.test(host)) {
    return host;
  }
  if (/\/openai$/.test(host)) {
    return `${host}/v1`;
  }
  return `${host}/openai/v1`;
};

export const resolveResponsesBaseUrl = (preferred?: string | null): string => {
  const host = resolveBaseHost(preferred);
  if (/\/v1$/.test(host)) {
    return host;
  }
  return `${host}/v1`;
};
