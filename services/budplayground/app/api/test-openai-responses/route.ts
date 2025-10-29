import { generateText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';

// Allow streaming responses up to 30 seconds
export const maxDuration = 300;

interface TestRequestBody {
  prompt?: string;
  model?: string;
  metadata?: {
    project_id?: string;
    base_url?: string;
  };
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

  console.log('[Test OpenAI Responses] Selected base URL source:', selected?.name);
  console.log('[Test OpenAI Responses] Selected base URL value:', selected?.value);

  let baseUrl = trimTrailingSlash(selected?.value || 'https://gateway.dev.bud.studio');

  // IMPORTANT: Responses API is only available on gateway, not on app
  // Replace app.dev.bud.studio with gateway.dev.bud.studio
  if (baseUrl.includes('app.dev.bud.studio')) {
    console.log('[Test OpenAI Responses] Detected app.dev.bud.studio, redirecting to gateway.dev.bud.studio');
    baseUrl = baseUrl.replace('app.dev.bud.studio', 'gateway.dev.bud.studio');
  }

  // Remove /openai/v1 suffix if present, but keep /v1
  baseUrl = baseUrl.replace(/\/openai\/v1$/, '');

  // Ensure baseURL ends with /v1 for OpenAI SDK compatibility
  if (!baseUrl.endsWith('/v1')) {
    baseUrl = `${baseUrl}/v1`;
  }

  console.log('[Test OpenAI Responses] Final base URL after cleanup:', baseUrl);

  return baseUrl;
};

export async function POST(req: Request) {
  const body: TestRequestBody = await req.json();

  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization && !apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  const prompt = body.prompt || 'Explain the concept of quantum entanglement in simple terms.';
  const model = body.model || 'gpt-4o';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  console.log('[Test OpenAI Responses] Using prompt:', prompt);
  console.log('[Test OpenAI Responses] Using model:', model);
  console.log('[Test OpenAI Responses] Using baseURL:', baseURL);

  // Extract the token
  let token = '';
  if (authorization) {
    token = authorization.replace(/^Bearer\s+/i, '');
  } else if (apiKey) {
    token = apiKey;
  }

  console.log('[Test OpenAI Responses] Token length:', token.length);

  try {
    // CRITICAL: Pass apiKey to createOpenAI so it adds proper Authorization header
    const proxyOpenAI = createOpenAI({
      baseURL,
      apiKey: token, // 🔥 THIS IS THE KEY - SDK will add "Authorization: Bearer <token>"
      fetch: (input, init) => {
        console.log('[Test OpenAI Responses] ========== CUSTOM FETCH ==========');
        console.log('[Test OpenAI Responses] URL:', input);
        console.log('[Test OpenAI Responses] Headers from SDK:', JSON.stringify(init?.headers, null, 2));

        // Only add additional headers like project-id
        const additionalHeaders: Record<string, string> = {};
        if (body.metadata?.project_id) {
          additionalHeaders['project-id'] = body.metadata.project_id;
        }

        // Merge SDK headers with additional headers
        const finalHeaders = {
          ...init?.headers,
          ...additionalHeaders,
        };

        console.log('[Test OpenAI Responses] Final headers:', JSON.stringify(finalHeaders, null, 2));
        console.log('[Test OpenAI Responses] =====================================');

        const request: RequestInit = {
          method: init?.method || 'POST',
          headers: finalHeaders,
          body: init?.body,
        };
        
        return fetch(input, request);
      },
    });

    console.log('[Test OpenAI Responses] Calling generateText with openai.responses()...');
    console.log('[Test OpenAI Responses] Using Responses API endpoint: POST /v1/responses');

    // Use the Responses API
    const result = await generateText({
      model: proxyOpenAI.responses(model),
      prompt,
    });

    console.log('[Test OpenAI Responses] Success!');
    console.log('[Test OpenAI Responses] Text:', result.text);
    console.log('[Test OpenAI Responses] Usage:', result.usage);
    console.log('[Test OpenAI Responses] Provider metadata:', JSON.stringify(result.providerMetadata, null, 2));

    return Response.json({
      success: true,
      text: result.text,
      usage: result.usage,
      finishReason: result.finishReason,
      providerMetadata: result.providerMetadata,
    });
  } catch (error: any) {
    console.error('[Test OpenAI Responses] Error:', error);
    console.error('[Test OpenAI Responses] Error message:', error?.message);
    console.error('[Test OpenAI Responses] Error stack:', error?.stack);

    // Extract the actual error message from the gateway response
    let actualError = error?.message ?? 'Failed to generate response';
    let errorDetails = error?.stack;

    // Check if there's a responseBody with the actual error from the gateway
    if (error?.responseBody) {
      console.error('[Test OpenAI Responses] Response body:', error.responseBody);
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