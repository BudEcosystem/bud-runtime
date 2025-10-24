import { smoothStream, streamText, createDataStreamResponse } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { copyCodeApiBaseUrl } from '@/app/lib/environment';
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

export async function POST(req: Request) {
  const body = await req.json();
  const {
    messages, // For ongoing chat
    id,
    model,
    metadata,
    // For initial prompt submission
    promptId,
    variables,
    input: unstructuredInput
  } = body;

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

  // If this is an initial prompt submission, fetch config and build messages
  if (promptId) {
    try {
      const promptConfig = await getPromptConfig(promptId, authorization, apiKey);

      // Build initial messages from prompt config
      finalMessages = buildInitialMessages(
        promptConfig,
        variables,
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
      }
    } catch (error) {
      return new Response(
        JSON.stringify({ error: 'Failed to fetch prompt configuration' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }
  }

  const proxyOpenAI = createOpenAI({
    baseURL: metadata?.base_url || copyCodeApiBaseUrl,
    fetch: (input, init) => {
      const request = {
        ...init,
        method: "POST",
        headers: {
          ...init?.headers,
          'project-id': metadata?.project_id,
          ...(authorization && { 'Authorization': authorization }),
          ...(apiKey && { 'api-key': apiKey }),
          'X-Forwarded-For': clientIp,
          'X-Real-IP': xRealIp || clientIp,
          'X-Original-Client-IP': clientIp,
          'X-Playground-Client-IP': xForwardedFor || xRealIp || cfConnectingIp || trueClientIp || 'unknown'
        },
        body: JSON.stringify({
          id,
          messages: finalMessages,
          model: deploymentModel,
          session_id: id,
          "stream_options": {
            "include_usage": true
          },
          "stream": true,
          max_completion_tokens: settings?.limit_response_length ? settings?.sequence_length : undefined,
          frequency_penalty: settings?.repeat_penalty ? settings.repeat_penalty : undefined,
          stop: settings?.stop_strings ? settings.stop_strings : undefined,
          temperature: settings?.temperature ? settings.temperature : undefined,
          extra_body: {
            "guided_json": settings?.enable_structured_json_schema && settings?.is_valid_json_schema ? settings?.structured_json_schema : undefined,
            "guided_decoding_backend": "outlines"
          }
        })
      };
      return fetch(input, request);
    }
  });

  const startTime = Date.now();
  let ttft = 0;
  const itls: number[] = [];
  let most_recent_time = startTime;

  return createDataStreamResponse({
    execute: dataStream => {
      const result = streamText({
        model: proxyOpenAI(deploymentModel),
        messages: finalMessages,
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
