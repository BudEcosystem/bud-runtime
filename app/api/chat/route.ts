// import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';

const openai = createOpenAI({
  // custom settings, e.g.
  compatibility: 'strict', // strict mode, enable when using the OpenAI API
  baseURL: "https://api.openai.com/v1/",
  apiKey: "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"
});

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id } = x

  console.log('chat id', id); // can be used for persisting the chat
  console.log('x', x); // can be used for persisting the chat

  // Call the language model
  const result = streamText({
    model: openai('gpt-4o'),
    messages,
    async onFinish({ text, toolCalls, toolResults, usage, finishReason }) {
      // implement your own logic here, e.g. for storing messages
      // or recording token usage
    },
  });

  // Respond with the stream
  return result.toDataStreamResponse();
}
