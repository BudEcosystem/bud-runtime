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

// Helper function to extract text from SDK's input array format
const extractTextFromInput = (input: any): string => {
  if (typeof input === 'string') {
    return input;
  }

  if (Array.isArray(input)) {
    const userMessage = input.find((msg: any) => msg.role === 'user');
    if (userMessage?.content) {
      if (Array.isArray(userMessage.content)) {
        const textContent = userMessage.content.find((c: any) => c.type === 'input_text' || c.type === 'text');
        return textContent?.text || '';
      }
      if (typeof userMessage.content === 'string') {
        return userMessage.content;
      }
    }
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

  console.log('[Prompt Chat] ===== REQUEST INFO =====');
  console.log('[Prompt Chat] Prompt input:', promptInput);
  console.log('[Prompt Chat] Model:', model);
  console.log('[Prompt Chat] Base URL:', baseURL);
  console.log('[Prompt Chat] Prompt ID:', body.prompt?.id);
  console.log('[Prompt Chat] Prompt version:', body.prompt?.version);
  console.log('[Prompt Chat] Prompt variables:', body.prompt?.variables);
  console.log('[Prompt Chat] =======================');

  try {
    const proxyOpenAI = createOpenAI({
      baseURL,
      fetch: (input, init) => {
        const modifiedInit = { ...init };

        try {
          if (modifiedInit?.body) {
            const bodyStr =
              typeof modifiedInit.body === 'string'
                ? modifiedInit.body
                : JSON.stringify(modifiedInit.body);

            const requestBody = JSON.parse(bodyStr);

            console.log('[Prompt Chat] ===== ORIGINAL SDK BODY =====');
            console.log(JSON.stringify(requestBody, null, 2));
            console.log('[Prompt Chat] ================================');

            // Remove the model field
            delete requestBody.model;

            // Convert input array to string
            if (requestBody.input) {
              const textInput = extractTextFromInput(requestBody.input);
              requestBody.input = textInput;
              console.log('[Prompt Chat] Converted input to string:', textInput);
            }

            // Add the prompt object with proper structure
            if (body.prompt?.id) {
              requestBody.prompt = {
                id: body.prompt.id,
                version: body.prompt.version || '1', // ← Make sure version has a default
                variables: body.prompt.variables || {}, // ← Make sure variables is always an object
                // deployment_name: 'qwen3-4b',
              };
              console.log('[Prompt Chat] Added prompt object:', JSON.stringify(requestBody.prompt, null, 2));
            }

            // ✅ ADD THIS: deployment_name is required by gateway
            // requestBody.deployment_name = 'qwen3-4b'; // or body.model, or a specific deployment name

            console.log('[Prompt Chat] ===== FINAL REQUEST BODY SENT TO GATEWAY =====');
            console.log(JSON.stringify(requestBody, null, 2));
            console.log('[Prompt Chat] =============================================');

            modifiedInit.body = JSON.stringify(requestBody);
          }
        } catch (err) {
          console.error('[Prompt Chat] Error modifying body:', err);
        }

        const request = {
          ...modifiedInit,
          method: 'POST',
          headers: {
            ...modifiedInit?.headers,
            ...(authorization && { 'Authorization': authorization }),
            ...(apiKey && { 'api-key': apiKey }),
            ...(body.metadata?.project_id && { 'project-id': body.metadata.project_id }),
          },
        };
        return fetch(input, request);
      },
    });

    console.log('[Prompt Chat] Calling generateText with openai.responses()...');

    const result = await generateText({
      model: proxyOpenAI.responses(model),
      prompt: promptInput,
      ...(body.settings?.temperature !== undefined && { temperature: body.settings.temperature }),
    });

    console.log('[Prompt Chat] Success!');
    console.log('[Prompt Chat] Text:', result.text);
    console.log('[Prompt Chat] Usage:', result.usage);

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

    let actualError = error?.message ?? 'Failed to generate response';

    if (error?.responseBody) {
      console.error('[Prompt Chat] Response body:', error.responseBody);
      try {
        const parsedError = JSON.parse(error.responseBody);
        if (parsedError?.error) {
          actualError = parsedError.error;
        }
      } catch (parseError) {
        actualError = error.responseBody;
      }
    }

    return Response.json(
      {
        success: false,
        error: actualError,
      },
      { status: 500 },
    );
  }
}