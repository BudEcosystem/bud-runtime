import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { randomUUID } from 'crypto';
import { NextResponse } from 'next/server';

export async function GET(req: Request) {
  const sessionId = req.url.split('/').pop();
  const authorization = req.headers.get('authorization');
  if (authorization) {
    try {
      const result = await axios
        .get(`${tempApiBaseUrl}/playground/chat-sessions/${sessionId}/messages`, {
          headers: {
            authorization: authorization,
          },
        })
        .then((response) => {
          return response.data.chat_messages;
        })
      return NextResponse.json(result);

    } catch (error: any) {
      return new NextResponse(error, { status: error.response?.status || 500 });
    }
  }
  return new NextResponse(null, { status: 401 });
}
