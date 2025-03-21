import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { randomUUID } from 'crypto';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();
  const authorization = req.headers.get('authorization');

  if (authorization) {
    try {
      const result = await axios
        .post(`${tempApiBaseUrl}/playground/messages`,
          body, {
          headers: {
            authorization: authorization,
          },
        })
        .then((response) => {
          return response.data?.chat_message;
        })

      return NextResponse.json(result);

    } catch (error: any) {
      return new NextResponse(error, { status: error.response?.status || 500 });
    }
  }
  return NextResponse.json({
    ...body,
    chat_session_id: body.chat_session_id || randomUUID(),
  });
}
