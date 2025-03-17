// import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { copyCodeApiBaseUrl } from '@/app/components/bud/environment';
import { ChatSettings } from '@/app/components/bud/chat/HistoryList';




// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id, model, metadata } = x
  const settings: ChatSettings = x.settings;
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization) {
    return new Response('Unauthorized', { status: 401 });
  }

  const proxyOpenAI = createOpenAI({
    // custom settings, e.g.
    baseURL: copyCodeApiBaseUrl,
    // apiKey: "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",
    fetch: (input, init) => {
      return fetch(input, {
        ...init,
        method: "POST",
        headers: {
          ...init?.headers,
          'project-id': metadata.project_id,
          'Authorization': authorization
        },
        body: init?.body ? JSON.stringify({
          id,
          messages,
          model,
          "stream": true,
          // ...settings,
          max_tokens: settings.limit_response_length ? settings?.sequence_length ? settings.sequence_length : 300 : undefined,
          frequency_penalty: settings?.repeat_penalty ? settings.repeat_penalty : undefined,
          stop: settings?.stop_strings ? settings.stop_strings : undefined,
          temperature: settings?.temperature ? settings.temperature : undefined,
          top_p: settings?.top_p_sampling ? settings.top_p_sampling : undefined,
        }) : undefined
      });
    }
  });

  // Call the language model
  const result = streamText({
    model: proxyOpenAI(model),
    messages,
    async onFinish({ text, toolCalls, toolResults, usage, finishReason }) {
      // implement your own logic here, e.g. for storing messages
      // or recording token usage
      console.log('onFinish', text);
      console.log('toolCalls', toolCalls);
      console.log('toolResults', toolResults);
      console.log('usage', usage);
      console.log('finishReason', finishReason);
    },
    onChunk({ chunk }) {
      console.log('chunk', chunk);
    },
    onError({ error }) {
      console.error('error', JSON.stringify(error, null, 2));
    },
    onStepFinish({ text, toolCalls, toolResults, usage }) {
      console.log('onStepFinish', text);
      console.log('toolCalls', toolCalls);
      console.log('toolResults', toolResults);
      console.log('usage', usage);
    }
  });

  // Respond with the stream
  return result.toDataStreamResponse();
}
