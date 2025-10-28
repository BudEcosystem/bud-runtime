interface PromptBody {
  input?: string | null;
  prompt?: {
    id?: string;
    version?: string | null;
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

  const defaultGateway =
    process.env.NEXT_PUBLIC_BUD_GATEWAY_BASE_URL ||
    process.env.BUD_GATEWAY_BASE_URL ||
    'https://gateway.dev.bud.studio';

  const host = (body.metadata?.base_url || defaultGateway).replace(/\/+$/, '');
  const url = `${host}/v1/responses`;

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
              version: body.prompt?.version ?? '1',
            }
          : undefined,
        input: promptInput,
        model: body.model,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return Response.json(data, { status: response.status });
    }

    return Response.json(data);
  } catch (error: any) {
    return Response.json(
      {
        error: error?.message ?? 'Failed to generate response',
      },
      { status: 500 }
    );
  }
}
