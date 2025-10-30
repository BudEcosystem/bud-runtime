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

  // Store the raw response for manual parsing if SDK fails
  let rawResponseBody: any = null;

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

            console.log('[Prompt Chat] Original SDK body:', JSON.stringify(requestBody, null, 2));

            // Delete the model field (as required by your gateway)
            delete requestBody.model;

            // Convert input array to string
            if (requestBody.input) {
              const textInput = extractTextFromInput(requestBody.input);
              requestBody.input = textInput;
            }

            // Add the prompt object
            if (body.prompt?.id) {
              requestBody.prompt = {
                id: body.prompt.id,
                version: body.prompt.version || '1',
                variables: body.prompt.variables || {},
              };
            }

            console.log('[Prompt Chat] Final request body:', JSON.stringify(requestBody, null, 2));

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

        // Intercept the response to capture raw body before SDK tries to parse it
        return fetch(input, request).then(async (response) => {
          const clonedResponse = response.clone();
          
          try {
            rawResponseBody = await clonedResponse.json();
            console.log('[Prompt Chat] Raw response captured:', JSON.stringify(rawResponseBody, null, 2));
          } catch (e) {
            console.error('[Prompt Chat] Failed to capture response:', e);
          }

          return response;
        });
      },
    });

    console.log('[Prompt Chat] Calling generateText with openai.responses()...');

    const result = await generateText({
      model: proxyOpenAI.responses(model),
      prompt: promptInput,
      ...(body.settings?.temperature !== undefined && { temperature: body.settings.temperature }),
    });

    // If we got here, SDK parsed successfully
    console.log('[Prompt Chat] Success via SDK!');
    console.log('[Prompt Chat] Text:', result.text);

    return Response.json({
      success: true,
      text: result.text,
      usage: result.usage,
      finishReason: result.finishReason,
      providerMetadata: result.providerMetadata,
    });

  } catch (error: any) {
    console.error('[Prompt Chat] SDK Error:', error);
    console.error('[Prompt Chat] Error name:', error?.name);

    // Check if it's a parsing error and we have the raw response
    if (error?.name === 'AI_InvalidResponseDataError' && rawResponseBody) {
      console.log('[Prompt Chat] SDK parsing failed, using manual extraction...');
      
      // Extract text manually from the raw response
      const text = extractTextFromGatewayResponse(rawResponseBody);

      if (text) {
        console.log('[Prompt Chat] Success via manual parsing!');
        console.log('[Prompt Chat] Extracted text:', text);

        return Response.json({
          success: true,
          text: text,
          usage: rawResponseBody.usage,
          finishReason: rawResponseBody.status,
          response: rawResponseBody,
        });
      }
    }

    // If manual parsing also failed, return error
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