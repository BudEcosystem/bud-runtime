// import { openai } from '@ai-sdk/openai';
import { streamText } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { copyCodeApiBaseUrl, tempApiBaseUrl } from '@/app/components/bud/environment';
import { ChatSettings } from '@/app/components/bud/chat/HistoryList';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
  // Extract the `messages` from the body of the request
  const x = await req.json()
  const { messages, id, model, metadata, chat } = x
  const settings: ChatSettings = x.settings;
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (!authorization) {
    return new Response('Unauthorized', { status: 401 });
  }


  console.log('metadata', metadata);
  console.log('authorization', authorization);

  const proxyOpenAI = createOpenAI({
    // custom settings, e.g.
    baseURL: copyCodeApiBaseUrl,
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
          "stream_options": {
            "include_usage": true
          },
          "stream": true,
          // ...settings,
          max_tokens: 3000,
          // max_tokens: settings.limit_response_length ? settings?.sequence_length > 100 ? settings.sequence_length : 3000 : 3000,
          frequency_penalty: settings?.repeat_penalty ? settings.repeat_penalty : undefined,
          stop: settings?.stop_strings ? settings.stop_strings : undefined,
          temperature: settings?.temperature ? settings.temperature : undefined,
          top_p: settings?.top_p_sampling ? settings.top_p_sampling : undefined,
        })
      }
      console.log('fetch', request);
      return fetch(input, request);
    }
  });

  // Call the language model
  const result = streamText({
    model: proxyOpenAI(model),
    messages,
    async onFinish(response) {
      // implement your own logic here, e.g. for storing messages
      // or recording token usage
      try {
        console.log('onFinish', JSON.stringify(response, null, 2));
        // const messageCreatePayload = {
        //   deployment_id: chat?.selectedDeployment?.id,
        //   e2e_latency: 0,
        //   input_tokens: 0,
        //   is_cache: false,
        //   output_tokens: 0,
        //   chat_session_id: chat?.id === NEW_SESSION ? undefined : chat?.id,
        //   prompt: messages[messages.length - 1].content,
        //   response: response,
        //   token_per_sec: 0,
        //   total_tokens: response?.usage.totalTokens,
        //   tpot: 0,
        //   ttft: 0,
        //   request_id: chat?.selectedDeployment?.id,
        // };
        // const result = await axios
        //   .post(`${tempApiBaseUrl}/playground/messages`,
        //     messageCreatePayload, {
        //     headers: {
        //       authorization: authorization,
        //     },
        //   })
        //   .then((response) => {
        //     return response.data?.chat_message;
        //   })
        console.log(`Saved message: ${result}`);
      } catch (error) {
        console.error('failed to save message');
      }
    },
    onChunk({ chunk }) {
      console.log('chunk', chunk);
    },
    onError({ error }) {
      console.error('error', JSON.stringify(error, null, 2));
    },
    onStepFinish(response) {
      console.log('onStepFinish', JSON.stringify(response, null, 2));
    }
  });

  // Respond with the stream
  return result.toDataStreamResponse();
}
