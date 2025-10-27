import { smoothStream, streamText, createDataStreamResponse } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { resolveGatewayBaseUrl } from '@/app/lib/gateway';
import { Settings } from '@/app/types/chat';
import axios from 'axios';
// Allow streaming responses up to 30 seconds
export const maxDuration = 300;

/**
 * Fetches prompt configuration from the gateway
 */
async function getPromptConfig(promptId: string, authHeader: string | null, apiKey: string | null) {
  try {
    const headers: any = {
      'Content-Type': 'application/json',
    };

    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    if (apiKey) {
      headers['api-key'] = apiKey;
    }

    const response = await axios.get(
      `https://app.dev.bud.studio/prompts/prompt-config/${promptId}`,
      { headers }
    );

    return response.data;
  } catch (error) {
    console.error('Failed to fetch prompt config:', error);
    throw error;
  }
}

/**
 * Builds initial messages from prompt config and user variables
 */
function buildInitialMessages(promptConfig: any, variables?: Record<string, any>, unstructuredInput?: string) {
  const messages: any[] = [];

  // Add system message if present in prompt config
  if (promptConfig.data?.messages) {
    for (const msg of promptConfig.data.messages) {
      if (msg.role === 'system') {
        messages.push({
          role: 'system',
          content: msg.content
        });
      }
    }
  }

  // Add user message
  if (unstructuredInput) {
    // Unstructured input - use as-is
    messages.push({
      role: 'user',
      content: unstructuredInput
    });
  } else if (variables) {
    // Structured input - format variables
    const variableText = Object.entries(variables)
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n');
    messages.push({
      role: 'user',
      content: variableText
    });
  }

  return messages;
}

const normalizeHeaders = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return { ...(headers as Record<string, string>) };
};

interface ResponseFormatConfig {
  schema?: Record<string, any>;
  name: string;
  description?: string;
}

const buildResponseFormat = (settings?: Settings): ResponseFormatConfig | undefined => {
  if (!settings?.enable_structured_json_schema || !settings?.is_valid_json_schema) {
    return undefined;
  }

  if (!settings.structured_json_schema) {
    return {
      name: 'structured_response',
    };
  }

  try {
    const schema = typeof settings.structured_json_schema === 'string'
      ? JSON.parse(settings.structured_json_schema)
      : settings.structured_json_schema;

    if (!schema || typeof schema !== 'object') {
      return undefined;
    }

    return {
      schema,
      name: (schema as { title?: string }).title || 'structured_response',
      description: (schema as { description?: string }).description,
    };
  } catch (error) {
    console.error('Invalid structured_json_schema supplied to response format:', error);
    return undefined;
  }
};

export async function POST(req: Request) {
  const body = await req.json();
  const {
    messages, // For ongoing chat
    id,
    model,
    metadata,
    // Legacy fields
    promptId,
    variables,
    input,
  } = body;

  const promptEnvelope = body.prompt ?? null;
  const effectivePromptId = promptEnvelope?.id ?? promptId;
  const promptVariables = promptEnvelope?.variables ?? variables;
  const promptVersion = promptEnvelope?.version;
  const unstructuredInput = input ?? body.unstructuredInput ?? null;

  const settings: Settings = body.settings;
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  // Extract client IP from headers
  const xForwardedFor = req.headers.get('x-forwarded-for');
  const xRealIp = req.headers.get('x-real-ip');
  const cfConnectingIp = req.headers.get('cf-connecting-ip');
  const trueClientIp = req.headers.get('true-client-ip');

  let clientIp = 'unknown';

  if (xForwardedFor) {
    clientIp = xForwardedFor;
  } else if (cfConnectingIp) {
    clientIp = cfConnectingIp;
  } else if (trueClientIp) {
    clientIp = trueClientIp;
  } else if (xRealIp) {
    clientIp = xRealIp;
  }

  // Accept either JWT (Bearer token) or API key
  if (!authorization && !apiKey) {
    return new Response('Unauthorized', { status: 401 });
  }

  // Determine the messages to use
  let finalMessages = messages;
  let deploymentModel = model;
  let responseFormat = buildResponseFormat(settings);

  // If this is an initial prompt submission, fetch config and build messages
  if (effectivePromptId) {
    try {
      const promptConfig = await getPromptConfig(effectivePromptId, authorization, apiKey);

      // Build initial messages from prompt config
      finalMessages = buildInitialMessages(
        promptConfig,
        promptVariables,
        unstructuredInput
      );

      // Use deployment from prompt config if available
      if (promptConfig.data?.deployment_name) {
        deploymentModel = promptConfig.data.deployment_name;
      }

      // Merge settings from prompt config if available
      if (promptConfig.data?.model_settings) {
        const promptSettings = promptConfig.data.model_settings;
        Object.assign(settings, {
          temperature: promptSettings.temperature ?? settings?.temperature,
          sequence_length: promptSettings.max_tokens ?? settings?.sequence_length,
          repeat_penalty: promptSettings.frequency_penalty ?? settings?.repeat_penalty,
          stop_strings: promptSettings.stop_sequences ?? settings?.stop_strings,
        });

        responseFormat = buildResponseFormat(settings);
      }
    } catch (error) {
      return new Response(
        JSON.stringify({ error: 'Failed to fetch prompt configuration' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }
  }

  const proxyOpenAI = createOpenAI({
    baseURL: resolveGatewayBaseUrl(metadata?.base_url),
    fetch: (input, init) => {
      let baseBody: Record<string, any> = {};
      if (init?.body && typeof init.body === 'string') {
        try {
          baseBody = JSON.parse(init.body);
        } catch (error) {
          console.error('Failed to parse OpenAI request body:', error);
        }
      }

      const requestHeaders = {
        ...normalizeHeaders(init?.headers),
          'project-id': metadata?.project_id,
          ...(authorization && { 'Authorization': authorization }),
          ...(apiKey && { 'api-key': apiKey }),
          'X-Forwarded-For': clientIp,
          'X-Real-IP': xRealIp || clientIp,
          'X-Original-Client-IP': clientIp,
          'X-Playground-Client-IP': xForwardedFor || xRealIp || cfConnectingIp || trueClientIp || 'unknown',
          'Content-Type': 'application/json',
        };

      const requestBody: Record<string, any> = {
        ...baseBody,
        id,
        session_id: id,
        stream_options: {
          include_usage: true,
        },
      };

      if (responseFormat) {
        requestBody.text = {
          ...(requestBody.text || {}),
          format: responseFormat.schema ? {
            type: 'json_schema',
            strict: true,
            name: responseFormat.name,
            description: responseFormat.description,
            schema: responseFormat.schema,
          } : { type: 'json_object' }
        };
      }

      return fetch(input, {
        ...init,
        method: "POST",
        headers: requestHeaders,
        body: JSON.stringify(requestBody),
      });
    }
  });

  const maxTokens = settings?.limit_response_length ? settings?.sequence_length : undefined;
  const temperature = typeof settings?.temperature === 'number' ? settings.temperature : undefined;
  const topP = typeof settings?.top_p_sampling === 'number' ? settings.top_p_sampling : undefined;
  const startTime = Date.now();
  let ttft = 0;
  const itls: number[] = [];
  let most_recent_time = startTime;

  return createDataStreamResponse({
    execute: dataStream => {
      console.log('[prompt-chat] invoking OpenAI responses API', {
        deploymentModel,
        messageCount: finalMessages?.length ?? 0,
        hasResponseFormat: Boolean(responseFormat),
      });

      const result = streamText({
        model: proxyOpenAI.responses(deploymentModel),
        messages: finalMessages,
        maxTokens,
        temperature,
        topP,
        experimental_transform: smoothStream({ delayInMs: 50 }),
        onChunk({ chunk }) {
          const current_time = Date.now();
          if (ttft === 0) {
            ttft = current_time - startTime;
          } else {
            itls.push(current_time - most_recent_time);
            most_recent_time = current_time;
          }
        },
        onFinish(response) {
          const endTime = Date.now();
          const duration = (endTime - startTime) / 1000;
          dataStream.writeMessageAnnotation({
            type: 'metrics',
            e2e_latency: Number(duration.toFixed(2)),
            ttft,
            throughput: Number((response.usage.completionTokens / duration).toFixed(2)),
            itl: Math.round((itls.reduce((a, b) => a + b, 0) / itls.length)),
          });
          console.log("console.complete")
          dataStream.writeData('call completed');
        },
      });

      result.mergeIntoDataStream(dataStream);
    },
    onError: error => {
      return error instanceof Error ? error.message : String(error);
    },
  });
}
