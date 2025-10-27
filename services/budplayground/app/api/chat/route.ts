// import { openai } from '@ai-sdk/openai';
import { smoothStream, streamText, createDataStreamResponse, generateId } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { resolveGatewayBaseUrl } from '@/app/lib/gateway';
import { Settings } from '@/app/types/chat';

// Allow streaming responses up to 30 seconds
export const maxDuration = 300;

interface ResponseFormatConfig {
  schema?: Record<string, any>;
  name: string;
  description?: string;
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
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id, model, metadata, chat } = x
  const settings: Settings = x.settings;
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  // Extract client IP from headers
  const xForwardedFor = req.headers.get('x-forwarded-for');
  const xRealIp = req.headers.get('x-real-ip');
  const cfConnectingIp = req.headers.get('cf-connecting-ip'); // Cloudflare
  const trueClientIp = req.headers.get('true-client-ip'); // Cloudflare Enterprise

  // In Kubernetes/production, pass the entire X-Forwarded-For chain
  // Let budgateway handle the logic of extracting the public IP
  let clientIp = 'unknown';
  let forwardedChain = '';

  const responseFormat = buildResponseFormat(settings);

  if (xForwardedFor) {
    // Pass the entire chain, budgateway will extract the public IP
    forwardedChain = xForwardedFor;
    clientIp = xForwardedFor; // Still use full chain for forwarding
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

  const proxyOpenAI = createOpenAI({
    // custom settings, e.g.
    baseURL: resolveGatewayBaseUrl(metadata.base_url),
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
          'project-id': metadata.project_id,
          // Pass through the authorization header (JWT Bearer token)
          ...(authorization && { 'Authorization': authorization }),
          // Pass through the API key header if present
          ...(apiKey && { 'api-key': apiKey }),
          // Forward the client IP to budgateway for accurate geolocation
          // Pass the entire chain for X-Forwarded-For so budgateway can find the public IP
          'X-Forwarded-For': clientIp,
          // For X-Real-IP, prefer the original value if present, otherwise use clientIp
          'X-Real-IP': xRealIp || clientIp,
          // Add custom headers that won't be modified by intermediate proxies
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
  const itls: number[] = []
  let most_recent_time = startTime

  return createDataStreamResponse({
    execute: dataStream => {
      const result = streamText({
        model: proxyOpenAI.responses(model),
        messages,
        maxTokens,
        temperature,
        topP,
        experimental_transform: smoothStream({delayInMs: 50}),
        onChunk({ chunk }) {
          // dataStream.writeMessageAnnotation({ chunk });
          const current_time = Date.now()
          if (ttft === 0) {
            ttft = current_time - startTime;
          } else {
            itls.push(current_time - most_recent_time)
            most_recent_time = current_time
          }
        },
        onFinish(response) {
          const endTime = Date.now();
          const duration = (endTime - startTime) / 1000;
          // message annotation:
          dataStream.writeMessageAnnotation({
            // id: generateId(), // e.g. id from saved DB record
            type: 'metrics',
            e2e_latency: Number(duration.toFixed(2)),
            ttft,
            throughput: Number((response.usage.completionTokens / duration).toFixed(2)),
            itl: Math.round((itls.reduce((a, b) => a + b, 0) / itls.length)),
          });

          // call annotation:
          dataStream.writeData('call completed');
        },
      });

      result.mergeIntoDataStream(dataStream);
    },
    onError: error => {
      // Error messages are masked by default for security reasons.
      // If you want to expose the error message to the client, you can do so here:
      return error instanceof Error ? error.message : String(error);
    },
  });
}
