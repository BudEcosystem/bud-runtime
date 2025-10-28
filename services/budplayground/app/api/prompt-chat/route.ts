import { generateText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { resolveGatewayBaseUrl } from '@/app/lib/gateway';

interface PromptBody {
  input?: string | null;
  prompt?: {
    id?: string;
    variables?: Record<string, string>;
  } | null;
  metadata?: {
    project_id?: string;
    base_url?: string | null;
  } | null;
  model?: string | null;
  settings?: {
    temperature?: number;
  } | null;
}

const normalizeHeaders = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...(headers as Record<string, string>) };
};

export async function POST(req: Request) {
  const body: PromptBody = await req.json();

  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization && !apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  const promptInput = (() => {
    if (body.input && body.input.trim().length > 0) {
      return body.input;
    }

    if (body.prompt?.variables) {
      return Object.entries(body.prompt.variables)
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n');
    }

    return '';
  })();

  if (!promptInput) {
    return Response.json(
      { error: 'Missing prompt input' },
      { status: 400 }
    );
  }

  const baseURL = resolveGatewayBaseUrl(body.metadata?.base_url ?? undefined, {
    ensureVersion: false,
  });

  const proxyOpenAI = createOpenAI({
    baseURL,
    fetch: (input, init) => {
      const headers = {
        ...normalizeHeaders(init?.headers),
        ...(body.metadata?.project_id && {
          'project-id': body.metadata.project_id,
        }),
        ...(authorization && { Authorization: authorization }),
        ...(apiKey && { 'api-key': apiKey }),
      };

      return fetch(input, {
        ...init,
        headers,
      });
    },
  });

  try {
    const result = await generateText({
      model: proxyOpenAI.responses(body.model || 'gpt-4o'),
      prompt: promptInput,
      temperature:
        typeof body.settings?.temperature === 'number'
          ? body.settings.temperature
          : undefined,
    });

    return Response.json({
      text: result.text,
      usage: result.usage,
    });
  } catch (error: any) {
    const upstreamStatus = error?.response?.status;
    const upstreamData = error?.response?.data;

    console.error('prompt-chat failure', {
      message: error?.message,
      baseURL,
      projectId: body.metadata?.project_id,
      upstreamStatus,
      upstreamData,
    });

    return Response.json(
      {
        error: upstreamData?.error ?? upstreamData?.message ?? 'Failed to generate response',
        details: upstreamData,
      },
      { status: upstreamStatus ?? 500 }
    );
  }
}
