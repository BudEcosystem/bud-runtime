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

  if (baseUrl.includes('app.dev.bud.studio')) {
    console.log('[Prompt Chat] Detected app.dev.bud.studio, redirecting to gateway.dev.bud.studio');
    baseUrl = baseUrl.replace('app.dev.bud.studio', 'gateway.dev.bud.studio');
  }

  baseUrl = baseUrl.replace(/\/openai\/v1$/, '');

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

// Extract text from gateway response
const extractTextFromGatewayResponse = (response: any): string => {
  if (!response.output || !Array.isArray(response.output)) {
    return '';
  }

  // Find the assistant message in output
  const assistantMessage = response.output.find((item: any) => 
    item.type === 'message' && item.role === 'assistant'
  );

  if (assistantMessage?.content && Array.isArray(assistantMessage.content)) {
    const textContent = assistantMessage.content.find((c: any) => 
      c.type === 'output_text' || c.type === 'text'
    );
    return textContent?.text || '';
  }

  return '';
};

export async function POST(req: Request) {
  const body: PromptBody = await req.json();

  console.log('[Prompt Chat] ===== INCOMING REQUEST BODY =====');
  console.log(JSON.stringify(body, null, 2));
  console.log('[Prompt Chat] ================================');

  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization && !apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  const promptInput = buildPromptInput(body);

  console.log('[Prompt Chat] Built prompt input:', promptInput);
  console.log('[Prompt Chat] body.input:', body.input);
  console.log('[Prompt Chat] body.prompt?.variables:', body.prompt?.variables);

  if (!promptInput) {
    return Response.json(
      { error: 'Missing prompt input' },
      { status: 400 },
    );
  }

  const model = body.model || 'qwen-4b-tools';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  console.log('[Prompt Chat] Using prompt input:', promptInput);
  console.log('[Prompt Chat] Using model:', model);
  console.log('[Prompt Chat] Using baseURL:', baseURL);
  console.log('[Prompt Chat] Prompt ID:', body.prompt?.id);

  try {
    // Build the request body
    const requestBody: any = {
      model: model,
      input: promptInput,
      temperature: body.settings?.temperature ?? 1,
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

    // Extract token
    let token = '';
    if (authorization) {
      console.log('[Prompt Chat] Authorization header received:', authorization);
      token = authorization.replace(/^Bearer\s+/i, '');
      console.log('[Prompt Chat] Extracted token from authorization:', token.substring(0, 20) + '...');
    } else if (apiKey) {
      console.log('[Prompt Chat] API key header received:', apiKey);
      token = apiKey;
      console.log('[Prompt Chat] Using api-key as token:', token.substring(0, 20) + '...');
    } else {
      console.log('[Prompt Chat] WARNING: No authorization or api-key header found!');
    }

    // Make direct fetch call to gateway
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };

    if (body.metadata?.project_id) {
      headers['project-id'] = body.metadata.project_id;
    }

    console.log('[Prompt Chat] Headers being sent to gateway:', {
      ...headers,
      Authorization: headers.Authorization.substring(0, 27) + '...' // Only show "Bearer " + first 20 chars
    });
    console.log('[Prompt Chat] Request URL:', `${baseURL}/responses`);

    const response = await fetch(`${baseURL}/responses`, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
    });

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

      return Response.json(
        { success: false, error: errorMessage },
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('[Prompt Chat] Gateway response:', JSON.stringify(result, null, 2));

    // Extract text from the gateway response
    const text = extractTextFromGatewayResponse(result);

    console.log('[Prompt Chat] Success!');
    console.log('[Prompt Chat] Extracted text:', text);
    console.log('[Prompt Chat] Usage:', result.usage);

    return Response.json({
      success: true,
      text: text,
      usage: result.usage,
      finishReason: result.status,
      response: result, // Include full response for debugging
    });
  } catch (error: any) {
    console.error('[Prompt Chat] Error:', error);
    console.error('[Prompt Chat] Error message:', error?.message);

    return Response.json(
      {
        success: false,
        error: error?.message ?? 'Failed to generate response',
      },
      { status: 500 },
    );
  }
}