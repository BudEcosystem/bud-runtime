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

  try {
    // Create OpenAI instance following the same pattern as chat route
    // DO NOT pass apiKey to createOpenAI - pass auth headers in custom fetch instead
    const openai = createOpenAI({
      baseURL,
      fetch: (input, init) => {
        console.log('[Test OpenAI Responses] ===== FETCH DETAILS =====');
        console.log('[Test OpenAI Responses] Full URL:', input);
        console.log('[Test OpenAI Responses] Method:', init?.method);

        // Build request with proper headers - following chat route pattern
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

        console.log('[Test OpenAI Responses] Final headers:', JSON.stringify(request.headers, null, 2));
        console.log('[Test OpenAI Responses] ===========================');

        const response = fetch(input, request);

        response.then(res => {
          console.log('[Test OpenAI Responses] Response status:', res.status);
          if (!res.ok) {
            res.clone().text().then(errorText => {
              console.error('[Test OpenAI Responses] Error response:', errorText);
            });
          }
        });

        return response;
      },
    });

    console.log('[Test OpenAI Responses] Calling generateText with openai.responses()...');
    console.log('[Test OpenAI Responses] Base URL configured:', baseURL);
    console.log('[Test OpenAI Responses] Using Responses API endpoint: POST /v1/responses');

    // Use the Responses API
    const result = await generateText({
      model: openai.responses(model),
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

    return Response.json(
      {
        success: false,
        error: error?.message ?? 'Failed to generate response',
        details: error?.stack,
      },
      { status: 500 },
    );
  }
}