// Allow streaming responses up to 30 seconds
export const maxDuration = 300;

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

  let baseUrl = trimTrailingSlash(selected?.value || 'https://gateway.dev.bud.studio');

  if (baseUrl.includes('app.dev.bud.studio')) {
    baseUrl = baseUrl.replace('app.dev.bud.studio', 'gateway.dev.bud.studio');
  }

  baseUrl = baseUrl.replace(/\/openai\/v1$/, '');

  if (!baseUrl.endsWith('/v1')) {
    baseUrl = `${baseUrl}/v1`;
  }

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

  const model = body.model || 'qwen-4b-tools';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  console.log('[Prompt Chat] Using model:', model);
  console.log('[Prompt Chat] Prompt input:', promptInput);
  console.log('[Prompt Chat] Base URL:', baseURL);

  try {
    // Build request body for gateway
    const requestBody: any = {
      input: promptInput,
      temperature: body.settings?.temperature ?? 1,
      stream: false, // Gateway doesn't actually stream despite accepting this param
    };

    // Add prompt object if provided
    if (body.prompt?.id) {
      requestBody.prompt = {
        id: body.prompt.id,
        version: body.prompt.version || '1',
        variables: body.prompt.variables || {},
      };
    }

    console.log('[Prompt Chat] Request body:', JSON.stringify(requestBody, null, 2));

    // Make direct fetch call to gateway
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(authorization && { 'Authorization': authorization }),
      ...(apiKey && { 'api-key': apiKey }),
      ...(body.metadata?.project_id && { 'project-id': body.metadata.project_id }),
    };

    console.log('[Prompt Chat] Sending request to:', `${baseURL}/responses`);

    const response = await fetch(`${baseURL}/responses`, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
    });

    console.log('[Prompt Chat] Response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Prompt Chat] Error response:', errorText);

      let errorMessage = 'Failed to generate response';
      try {
        const errorJson = JSON.parse(errorText);
        errorMessage = errorJson.error || errorMessage;
      } catch (e) {
        errorMessage = errorText;
      }

      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('[Prompt Chat] Gateway response received');

    // Extract text from gateway's response format
    let text = '';
    if (result.output && Array.isArray(result.output)) {
      for (const item of result.output) {
        if (item.content && Array.isArray(item.content)) {
          for (const content of item.content) {
            if (content.text) {
              text += content.text;
            }
          }
        }
      }
    }

    console.log('[Prompt Chat] Extracted text length:', text.length);

    // Create a streaming response for useChat
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        // Send the text as a stream chunk
        controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`));

        // Send usage metadata if available
        if (result.usage) {
          controller.enqueue(encoder.encode(`d:${JSON.stringify({
            finishReason: result.status,
            usage: result.usage
          })}\n`));
        }

        controller.close();
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'X-Vercel-AI-Data-Stream': 'v1',
      },
    });

  } catch (error: any) {
    console.error('[Prompt Chat] Error:', error);
    console.error('[Prompt Chat] Error message:', error?.message);

    // Handle errors
    let actualError = error?.message ?? 'Failed to generate response';

    if (error?.responseBody) {
      try {
        const parsedError = JSON.parse(error.responseBody);
        if (parsedError?.error) {
          actualError = typeof parsedError.error === 'string'
            ? parsedError.error
            : parsedError.error.message || actualError;
        }
      } catch (e) {
        actualError = error.responseBody;
      }
    }

    return Response.json(
      {
        error: actualError,
      },
      { status: 500 },
    );
  }
}