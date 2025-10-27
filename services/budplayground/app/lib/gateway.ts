import { apiBaseUrl, copyCodeApiBaseUrl, tempApiBaseUrl } from './environment';

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const ensureOpenAIPath = (value: string) => {
  const trimmed = trimTrailingSlash(value);
  return /\/openai(\/|$)/.test(trimmed) ? trimmed : `${trimmed}/openai/v1`;
};

const candidateEnvValues = () => [
  copyCodeApiBaseUrl,
  tempApiBaseUrl,
  apiBaseUrl,
  process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL,
  process.env.NEXT_PUBLIC_TEMP_API_BASE_URL,
  process.env.NEXT_PUBLIC_BASE_URL,
  process.env.BUD_GATEWAY_BASE_URL,
];

export const resolveGatewayBaseUrl = (preferred?: string | null): string => {
  const candidates = [preferred, ...candidateEnvValues(), 'http://localhost:8000'];

  for (const candidate of candidates) {
    if (candidate && typeof candidate === 'string') {
      const trimmed = candidate.trim();
      if (trimmed.length > 0) {
        return ensureOpenAIPath(trimmed);
      }
    }
  }

  return 'http://localhost:8000/openai/v1';
};
