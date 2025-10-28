import { resolveResponsesBaseUrl } from '@/app/lib/gateway';

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

  const baseURL = resolveResponsesBaseUrl(body.metadata?.base_url ?? 'https://gateway.dev.bud.studio');
  const url = `${baseURL}/responses`;

  console.debug('[prompt-chat] prepared request', {
    url,
    projectId: body.metadata?.project_id,
    promptPreview: promptInput.slice(0, 120),
    promptLength: promptInput.length,
  });

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(body.metadata?.project_id && {
          'project-id': body.metadata.project_id,
        }),
        ...(authorization && { Authorization: authorization }),
        ...(apiKey && { 'api-key': apiKey }),
      },
      body: JSON.stringify({
        prompt: body.prompt?.id
          ? {
              id: body.prompt.id,
              version: '1',
            }
          : undefined,
        input: promptInput,
        model: body.model,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error('prompt-chat failure', { status: response.status, data });
      return Response.json(data, { status: response.status });
    }

    return Response.json(data);
  } catch (error: any) {
    console.error('prompt-chat network failure', error);
    return Response.json(
      {
        error: error?.message ?? 'Failed to generate response',
      },
      { status: 500 }
    );
  }
}
