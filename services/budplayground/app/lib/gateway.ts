import { apiBaseUrl, copyCodeApiBaseUrl, tempApiBaseUrl } from './environment';

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const ensureOpenAIPath = (value: string, options?: { ensureVersion?: boolean }) => {
  const trimmed = trimTrailingSlash(value);
  if (/\/openai\/v1(\/|$)/.test(trimmed)) {
    if (options?.ensureVersion === false) {
      return trimmed.replace(/\/openai\/v1(\/|$)/, '/openai$1');
    }
    return trimmed;
  }

  if (/\/openai(\/|$)/.test(trimmed)) {
    if (options?.ensureVersion === false) {
      return trimmed;
    }
    return `${trimmed}/v1`;
  }

  return options?.ensureVersion === false
    ? `${trimmed}/openai`
    : `${trimmed}/openai/v1`;
};

const stripOpenAIPath = (value: string) => value.replace(/\/openai(\/v1)?$/, '');

const candidateEnvValues = () => [
  copyCodeApiBaseUrl,
  tempApiBaseUrl,
  apiBaseUrl,
  process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL,
  process.env.NEXT_PUBLIC_TEMP_API_BASE_URL,
  process.env.NEXT_PUBLIC_BASE_URL,
  process.env.BUD_GATEWAY_BASE_URL,
];

const resolveBaseHost = (preferred?: string | null): string => {
  const candidates = [preferred, ...candidateEnvValues(), 'http://localhost:8000'];

  for (const candidate of candidates) {
    if (candidate && typeof candidate === 'string') {
      const trimmed = candidate.trim();
      if (trimmed.length > 0) {
        return trimTrailingSlash(trimmed);
      }
    }
  }

  return 'http://localhost:8000';
};

export const resolveGatewayBaseUrl = (
  preferred?: string | null,
  options?: { ensureVersion?: boolean }
): string => {
  return ensureOpenAIPath(resolveBaseHost(preferred), options);
};

export const resolveResponsesBaseUrl = (preferred?: string | null): string => {
  const base = stripOpenAIPath(resolveBaseHost(preferred));
  return `${trimTrailingSlash(base)}/v1`;
};
