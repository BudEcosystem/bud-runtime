import { generateText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';

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

  console.log('[Prompt Chat] Selected base URL source:', selected?.name);
  console.log('[Prompt Chat] Selected base URL value:', selected?.value);

  let baseUrl = trimTrailingSlash(selected?.value || 'https://gateway.dev.bud.studio');

  // IMPORTANT: Responses API is only available on gateway, not on app
  // Replace app.dev.bud.studio with gateway.dev.bud.studio
  if (baseUrl.includes('app.dev.bud.studio')) {
    console.log('[Prompt Chat] Detected app.dev.bud.studio, redirecting to gateway.dev.bud.studio');
    baseUrl = baseUrl.replace('app.dev.bud.studio', 'gateway.dev.bud.studio');
  }

  // Remove /openai/v1 suffix if present, but keep /v1
  baseUrl = baseUrl.replace(/\/openai\/v1$/, '');

  // Ensure baseURL ends with /v1 for OpenAI SDK compatibility
  if (!baseUrl.endsWith('/v1')) {
    baseUrl = `${baseUrl}/v1`;
  }

  console.log('[Prompt Chat] Final base URL after cleanup:', baseUrl);

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

  const model = body.model || 'gpt-4o';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  console.log('[Prompt Chat] Using prompt input:', promptInput);
  console.log('[Prompt Chat] Using model:', model);
  console.log('[Prompt Chat] Using baseURL:', baseURL);
  console.log('[Prompt Chat] Prompt ID:', body.prompt?.id);
  console.log('[Prompt Chat] Prompt version:', body.prompt?.version);

  try {
    // Create OpenAI instance following the same pattern as chat route
    // DO NOT pass apiKey to createOpenAI - pass auth headers in custom fetch instead
    const proxyOpenAI = createOpenAI({
      baseURL,
      fetch: (input, init) => {
        const request = {
          ...init,
          method: 'POST',
          headers: {
            ...init?.headers,
            // Pass through the authorization header (JWT Bearer token)
            ...(authorization && { 'Authorization': authorization }),
            // Pass through the API key header if present
            ...(apiKey && { 'api-key': apiKey }),
            // Add project-id if provided
            ...(body.metadata?.project_id && { 'project-id': body.metadata.project_id }),
          },
        };
        return fetch(input, request);
      },
    });

    console.log('[Prompt Chat] Calling generateText with openai.responses()...');
    console.log('[Prompt Chat] Base URL configured:', baseURL);
    console.log('[Prompt Chat] Using Responses API endpoint: POST /v1/responses');

    // Use the Responses API
    const result = await generateText({
      model: proxyOpenAI.responses(model),
      prompt: promptInput,
      ...(body.settings?.temperature !== undefined && { temperature: body.settings.temperature }),
    });

    console.log('[Prompt Chat] Success!');
    console.log('[Prompt Chat] Text:', result.text);
    console.log('[Prompt Chat] Usage:', result.usage);
    console.log('[Prompt Chat] Provider metadata:', JSON.stringify(result.providerMetadata, null, 2));

    return Response.json({
      success: true,
      text: result.text,
      usage: result.usage,
      finishReason: result.finishReason,
      providerMetadata: result.providerMetadata,
    });
  } catch (error: any) {
    console.error('[Prompt Chat] Error:', error);
    console.error('[Prompt Chat] Error message:', error?.message);
    console.error('[Prompt Chat] Error stack:', error?.stack);

    // Extract the actual error message from the gateway response
    let actualError = error?.message ?? 'Failed to generate response';
    let errorDetails = error?.stack;

    // Check if there's a responseBody with the actual error from the gateway
    if (error?.responseBody) {
      console.error('[Prompt Chat] Response body:', error.responseBody);
      try {
        const parsedError = JSON.parse(error.responseBody);
        if (parsedError?.error) {
          actualError = parsedError.error;
        }
      } catch (parseError) {
        // If parsing fails, use the raw responseBody
        actualError = error.responseBody;
      }
    }

    return Response.json(
      {
        success: false,
        error: actualError,
        details: errorDetails,
      },
      { status: 500 },
    );
  }
}
