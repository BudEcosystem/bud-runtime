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

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const resolveGatewayBase = (preferred?: string | null) => {
  const fallbackHosts = [
    { name: 'NEXT_PUBLIC_BUD_GATEWAY_BASE_URL', value: process.env.NEXT_PUBLIC_BUD_GATEWAY_BASE_URL },
    { name: 'BUD_GATEWAY_BASE_URL', value: process.env.BUD_GATEWAY_BASE_URL },
    { name: 'NEXT_PUBLIC_COPY_CODE_API_BASE_URL', value: process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL },
    { name: 'NEXT_PUBLIC_TEMP_API_BASE_URL', value: process.env.NEXT_PUBLIC_TEMP_API_BASE_URL },
    { name: 'NEXT_PUBLIC_BASE_URL', value: process.env.NEXT_PUBLIC_BASE_URL },
    { name: 'hardcoded', value: 'https://gateway.dev.bud.studio' },
  ];

  const selected = [{ name: 'preferred', value: preferred }, ...fallbackHosts].find(
    (item) => typeof item.value === 'string' && item.value.trim().length > 0,
  );

  console.log('[Responses API] Selected base URL source:', selected?.name);
  console.log('[Responses API] Selected base URL value:', selected?.value);

  let baseUrl = trimTrailingSlash(selected?.value || 'https://gateway.dev.bud.studio');

  // IMPORTANT: Responses API is only available on gateway, not on app
  // Replace app.dev.bud.studio with gateway.dev.bud.studio
  if (baseUrl.includes('app.dev.bud.studio')) {
    console.log('[Responses API] Detected app.dev.bud.studio, redirecting to gateway.dev.bud.studio');
    baseUrl = baseUrl.replace('app.dev.bud.studio', 'gateway.dev.bud.studio');
  }

  // Remove /openai/v1 or /v1 suffix if present, since we'll add /v1/responses
  baseUrl = baseUrl.replace(/\/openai\/v1$/, '');
  baseUrl = baseUrl.replace(/\/v1$/, '');

  console.log('[Responses API] Final base URL after cleanup:', baseUrl);

  return baseUrl;
};

const buildPromptInput = (body: PromptBody) => {
  if (body.input && body.input.trim().length > 0) {
    return body.input;
  }

  if (body.prompt?.variables) {
    return Object.entries(body.prompt.variables)
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n');
  }

  return '';
};

export async function POST(req: Request) {
  const body: PromptBody = await req.json();

  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization && !apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  const promptInput = buildPromptInput(body);

  if (!promptInput) {
    return Response.json(
      { error: 'Missing prompt input' },
      { status: 400 },
    );
  }

  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);
  const responsesEndpoint = `${baseURL}/v1/responses`;

  // Build request body matching gateway's expected format
  const requestBody: {
    prompt: {
      id: string;
      version?: string;
    };
    input: string;
    model?: string;
    temperature?: number;
  } = {
    prompt: {
      id: body.prompt?.id || '',
    },
    input: promptInput,
  };

  // Add optional fields
  if (body.prompt?.version) {
    requestBody.prompt.version = body.prompt.version;
  }
  if (body.model) {
    requestBody.model = body.model;
  }
  if (body.settings?.temperature !== undefined) {
    requestBody.temperature = body.settings.temperature;
  }

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (authorization) {
    headers['Authorization'] = authorization;
  }
  if (apiKey) {
    headers['api-key'] = apiKey;
  }
  if (body.metadata?.project_id) {
    headers['project-id'] = body.metadata.project_id;
  }

  // Log the request
  console.log('[Responses API] Endpoint:', responsesEndpoint);
  console.log('[Responses API] Request body:', JSON.stringify(requestBody, null, 2));
  console.log('[Responses API] Request headers:', headers);

  try {
    const response = await fetch(responsesEndpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
    });

    console.log('[Responses API] Response status:', response.status);
    console.log('[Responses API] Response statusText:', response.statusText);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Responses API] Error response:', errorText);

      let errorData;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { error: errorText || 'Failed to generate response' };
      }

      return Response.json(errorData, { status: response.status });
    }

    const data = await response.json();
    console.log('[Responses API] Success response:', JSON.stringify(data, null, 2));

    return Response.json(data);
  } catch (error: any) {
    console.error('[Responses API] Request error:', error);

    return Response.json(
      {
        error: error?.message ?? 'Failed to generate response',
      },
      { status: 500 },
    );
  }
}
