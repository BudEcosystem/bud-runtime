// import { openai } from '@ai-sdk/openai';
import { smoothStream, streamText, createDataStreamResponse, generateId } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { copyCodeApiBaseUrl, tempApiBaseUrl } from '@/app/lib/environment';
import { Settings } from '@/app/types/chat';

// Allow streaming responses up to 30 seconds
export const maxDuration = 300;

export async function POST(req: Request) {
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id, model, metadata, chat } = x
  const settings: Settings = x.settings;
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization) {
    return new Response('Unauthorized', { status: 401 });
  }

  const proxyOpenAI = createOpenAI({
    // custom settings, e.g.
    baseURL: metadata.base_url || copyCodeApiBaseUrl,
    // apiKey: "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",
    fetch: (input, init) => {
      const request = {
        ...init,
        method: "POST",
        headers: {
          ...init?.headers,
          'project-id': metadata.project_id,
          'Authorization': authorization
        },
        body: JSON.stringify({
          id,
          messages,
          model,
          session_id: id,
          "stream_options": {
            "include_usage": true
          },
          "stream": true,
          // ...settings,
          // max_tokens: 3000,
          max_completion_tokens: settings?.limit_response_length ? settings?.sequence_length : undefined,
          frequency_penalty: settings?.repeat_penalty ? settings.repeat_penalty : undefined,
          stop: settings?.stop_strings ? settings.stop_strings : undefined,
          temperature: settings?.temperature ? settings.temperature : undefined,
          top_p: settings?.top_p_sampling ? settings.top_p_sampling : undefined,
          extra_body:{
            "guided_json": settings?.enable_structured_json_schema && settings?.is_valid_json_schema ? settings?.structured_json_schema : undefined,
            "guided_decoding_backend": "outlines"
          }
        })
      }
      console.log('fetch', request);
      return fetch(input, request);
    }
  });

  const startTime = Date.now();
  let ttft = 0;
  const itls: number[] = []
  let most_recent_time = startTime

  return createDataStreamResponse({
    execute: dataStream => {
      const result = streamText({
        model: proxyOpenAI(model),
        messages,
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
