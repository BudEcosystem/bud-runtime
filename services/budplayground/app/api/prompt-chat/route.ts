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
  messages?: Array<{
    role: string;
    content: string;
  }>;
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

  // Check if this is a follow-up message in a conversation
  const isFollowUpMessage = body.messages && body.messages.length > 1;

  const promptInput = buildPromptInput(body);

  // For initial prompt submission, we need prompt input
  // For follow-up messages, we rely on the messages array
  if (!promptInput && !isFollowUpMessage) {
    return Response.json(
      { error: 'Missing prompt input or messages' },
      { status: 400 },
    );
  }

  const model = body.model || 'qwen-4b-tools';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  console.log('[Prompt Chat] Using model:', model);
  console.log('[Prompt Chat] Is follow-up message:', isFollowUpMessage);
  console.log('[Prompt Chat] Messages count:', body.messages?.length || 0);
  console.log('[Prompt Chat] Prompt input:', promptInput);
  console.log('[Prompt Chat] Base URL:', baseURL);

  try {
    // Check if this is a structured prompt (has variables)
    const hasStructuredInput = body.prompt?.variables && Object.keys(body.prompt.variables).length > 0;

    console.log('[Prompt Chat] Has structured input:', hasStructuredInput);

    // Build request body for gateway
    const requestBody: any = {
      temperature: body.settings?.temperature ?? 1,
      // stream: false, // Gateway doesn't actually stream despite accepting this param
    };

    if (isFollowUpMessage) {
      // For follow-up messages, include the conversation history
      console.log('[Prompt Chat] Building request for follow-up message');

      requestBody.messages = body.messages;

      // Still include prompt context (id and version) but NOT variables
      if (body.prompt?.id) {
        requestBody.prompt = {
          id: body.prompt.id,
          version: body.prompt.version || '1',
        };
      }
    } else {
      // For initial prompt submission, use the original approach
      console.log('[Prompt Chat] Building request for initial prompt submission');

      // Only include input field for unstructured prompts
      if (!hasStructuredInput && promptInput) {
        requestBody.input = promptInput;
      }

      // Add prompt object with variables if provided
      if (body.prompt?.id) {
        // Transform variable keys: replace spaces with underscores
        const transformedVariables: Record<string, string> = {};
        if (body.prompt.variables) {
          Object.entries(body.prompt.variables).forEach(([key, value]) => {
            const transformedKey = key.replace(/\s+/g, '_');
            transformedVariables[transformedKey] = String(value);
          });
        }

        requestBody.prompt = {
          id: body.prompt.id,
          version: body.prompt.version || '1',
          variables: transformedVariables,
        };
      }
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
    console.log('[Prompt Chat] Response content-type:', response.headers.get('content-type'));

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

    // Get the response as text first
    const responseText = await response.text();
    console.log('[Prompt Chat] Response text preview:', responseText.substring(0, 200));

    let text = '';
    let usage: any = null;
    let finishReason = 'completed';

    // Check if it's SSE format (starts with "event:")
    if (responseText.startsWith('event:')) {
      console.log('[Prompt Chat] Parsing SSE format response');

      // Parse SSE stream
      const lines = responseText.split('\n');
      let currentEvent = '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          const data = line.substring(5).trim();

          try {
            const parsed = JSON.parse(data);

            // Extract text from content deltas
            if (currentEvent === 'content_delta' || currentEvent === 'output') {
              if (parsed.delta) {
                text += parsed.delta;
              } else if (parsed.content && Array.isArray(parsed.content)) {
                for (const content of parsed.content) {
                  if (content.text) {
                    text += content.text;
                  }
                }
              }
            }

            // Extract usage and finish reason from response_end
            if (currentEvent === 'response_end' || currentEvent === 'done') {
              if (parsed.usage) {
                usage = parsed.usage;
              }
              if (parsed.status) {
                finishReason = parsed.status;
              }
            }
          } catch (e) {
            console.warn('[Prompt Chat] Failed to parse SSE data:', data);
          }
        }
      }

      console.log('[Prompt Chat] Extracted text from SSE:', text.substring(0, 100));
    } else {
      // Try to parse as JSON (fallback)
      console.log('[Prompt Chat] Parsing JSON format response');

      try {
        const result = JSON.parse(responseText);

        // Extract text from gateway's response format
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

        usage = result.usage;
        finishReason = result.status || 'completed';
      } catch (e) {
        console.error('[Prompt Chat] Failed to parse response as JSON:', e);
        throw new Error('Failed to parse gateway response');
      }
    }

    console.log('[Prompt Chat] Final extracted text length:', text.length);

    // Create a streaming response for useChat
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        // Send the text as a stream chunk
        controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`));

        // Send usage metadata if available
        if (usage) {
          controller.enqueue(encoder.encode(`d:${JSON.stringify({
            finishReason: finishReason,
            usage: usage
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
