// import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { copyCodeApiBaseUrl } from '@/app/components/bud/environment';




// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id, model, metadata } = x
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization) {
    return new Response('Unauthorized', { status: 401 });
  }

  console.log('chat id', id); // can be used for persisting the chat
  console.log('x', x); // can be used for persisting the chat
  const payload = {
    // custom settings, e.g.
    baseURL: copyCodeApiBaseUrl,
    // apiKey: "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",
    headers: {
      'Authorization': authorization,
      // 'Authorization': 'Bearer budserve_NgMnHOzyQjCXGgmoFZrYNwS7LgqZU2VMcmz3bz4U',
      'project-id': metadata.project_id,
    },
  };
  console.log('apiKey', apiKey);
  console.log('payload', payload);
  const proxyOpenAI = createOpenAI(payload);

  // Call the language model
  const result = streamText({
    model: proxyOpenAI(model),
    messages,
    async onFinish({ text, toolCalls, toolResults, usage, finishReason }) {
      console.log('text', text);
      console.log('toolCalls', toolCalls);
      console.log('toolResults', toolResults);
      console.log('usage', usage);
      console.log('finishReason', finishReason);
      // implement your own logic here, e.g. for storing messages
      // or recording token usage
    },
    onChunk({ chunk }) {
      console.log('chunk', chunk);
    },
    onError({ error }) {
      console.error('error', JSON.stringify(error, null, 2));
    },
    onStepFinish({ text, toolCalls, toolResults, usage }) {
      console.log('text', text);
      console.log('toolCalls', toolCalls);
      console.log('toolResults', toolResults);
      console.log('usage', usage);
    }
  });

  // Respond with the stream
  return result.toDataStreamResponse();
}
