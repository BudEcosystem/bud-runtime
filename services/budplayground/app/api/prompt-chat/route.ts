import { Logger, extractErrorMessage, categorizeError } from '@/app/lib/logger';

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
  const logger = new Logger({ endpoint: 'Prompt Chat', method: 'POST' });

  let body: PromptBody;
  try {
    body = await req.json();
  } catch (error) {
    logger.error('Failed to parse request body', error);
    return Response.json(
      { error: 'Invalid JSON in request body' },
      { status: 400 },
    );
  }

  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  // Log request details (sanitized)
  const headers: Record<string, string> = {
    'authorization': authorization || 'missing',
    'api-key': apiKey || 'missing',
  };
  logger.logRequest(body, headers);

  if (!authorization && !apiKey) {
    logger.error('Missing authentication credentials');
    return new Response('Unauthorized', { status: 401 });
  }

  // Check if this is a follow-up message in a conversation
  const isFollowUpMessage = body.messages && body.messages.length > 1;

  const promptInput = buildPromptInput(body);

  // For initial prompt submission, we need prompt input
  // For follow-up messages, we rely on the messages array
  if (!promptInput && !isFollowUpMessage) {
    logger.warn('Missing prompt input or messages', { promptInput, isFollowUpMessage });
    return Response.json(
      { error: 'Missing prompt input or messages' },
      { status: 400 },
    );
  }

  const model = body.model || 'qwen-4b-tools';
  const baseURL = resolveGatewayBase(body.metadata?.base_url ?? null);

  logger.info(`Using model: ${model}, Gateway URL: ${baseURL}`);

  try {
    // Check if this is a structured prompt (has variables)
    const hasStructuredInput = body.prompt?.variables && Object.keys(body.prompt.variables).length > 0;

    // Build request body for gateway
    const requestBody: any = {
      temperature: body.settings?.temperature ?? 1,
      // stream: false, // Gateway doesn't actually stream despite accepting this param
    };

    if (isFollowUpMessage) {
      // For follow-up messages, include the conversation history
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

    // Make direct fetch call to gateway
    const gatewayHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(authorization && { 'Authorization': authorization }),
      ...(apiKey && { 'api-key': apiKey }),
      ...(body.metadata?.project_id && { 'project-id': body.metadata.project_id }),
    };

    const gatewayUrl = `${baseURL}/responses`;
    logger.logGatewayRequest(gatewayUrl, 'POST', gatewayHeaders, requestBody);

    const response = await fetch(gatewayUrl, {
      method: 'POST',
      headers: gatewayHeaders,
      body: JSON.stringify(requestBody),
    });

    logger.info(`Gateway response status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      logger.logGatewayResponse(response.status, errorText);

      // Parse error message properly
      let errorMessage = 'Failed to generate response';
      let errorJson: any = null;

      try {
        errorJson = JSON.parse(errorText);
        // Use the new extractErrorMessage utility to properly extract the message
        errorMessage = extractErrorMessage(errorJson);
      } catch (e) {
        // If parsing fails, use the raw text
        errorMessage = errorText || errorMessage;
      }

      logger.error('Gateway returned error', {
        status: response.status,
        errorMessage,
        rawResponse: errorText.substring(0, 500),
      });

      // Categorize the error for user-friendly message
      const categorized = categorizeError(response.status, errorMessage);

      // Throw with both technical and user-friendly messages
      const error: any = new Error(categorized.userMessage);
      error.technicalMessage = categorized.technicalMessage;
      error.category = categorized.category;
      error.statusCode = response.status;

      throw error;
    }

    // Get the response as text first
    const responseText = await response.text();
    logger.logGatewayResponse(response.status, responseText);

    let text = '';
    let usage: any = null;
    let finishReason = 'completed';

    // Check if it's SSE format (starts with "event:")
    if (responseText.startsWith('event:')) {
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
    } else {
      // Try to parse as JSON (fallback)
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
    // Log detailed error information
    logger.error('Failed to process prompt chat request', error, {
      category: error?.category,
      statusCode: error?.statusCode,
      technicalMessage: error?.technicalMessage,
    });

    // Determine the user-facing error message
    let userMessage = 'Failed to generate response';
    let technicalMessage = error?.message || userMessage;
    let statusCode = 500;

    // If we have a categorized error from the gateway
    if (error?.category && error?.statusCode) {
      userMessage = error.message; // Already user-friendly from categorizeError
      technicalMessage = error.technicalMessage || error.message;
      statusCode = error.statusCode;
    } else if (error?.responseBody) {
      // Legacy error handling for other error formats
      try {
        const parsedError = JSON.parse(error.responseBody);
        technicalMessage = extractErrorMessage(parsedError);
        const categorized = categorizeError(statusCode, technicalMessage);
        userMessage = categorized.userMessage;
      } catch (e) {
        technicalMessage = error.responseBody;
      }
    } else if (error?.message) {
      // Extract from standard Error object
      technicalMessage = error.message;
      const categorized = categorizeError(statusCode, technicalMessage);
      userMessage = categorized.userMessage;
    }

    // Log final error response
    logger.error('Returning error response', {
      statusCode,
      userMessage,
      technicalMessage,
    });

    // Return structured error response
    return Response.json(
      {
        error: userMessage,
        details: process.env.NODE_ENV === 'development' ? technicalMessage : undefined,
      },
      { status: statusCode },
    );
  }
}
