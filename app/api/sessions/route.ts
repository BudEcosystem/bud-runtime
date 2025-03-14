import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { randomUUID } from 'crypto';
import { NextResponse } from 'next/server';

export async function GET(req: Request) {
  const authorization = req.headers.get('authorization');
  if (authorization) {
    try {
      const result = await axios
        .get(`${tempApiBaseUrl}/playground/chat-sessions`, {
          headers: {
            authorization: authorization,
          },
        })
        .then((response) => {
          return response.data.chat_sessions;
        })
      return NextResponse.json(result);

    } catch (error: any) {
      return new NextResponse(error, { status: error.response?.status || 500 });
    }
  }
  return NextResponse.json([]);

}


export async function POST(req: Request) {
  const body = await req.json();
  const authorization = req.headers.get('authorization');

  if (authorization) {
    try {
      const result = await axios
        .post(`${tempApiBaseUrl}/playground/messages`,
          body,
          {
            headers: {
              authorization: authorization,
            },
          })
        .then((response) => {
          return response.data?.chat_message
        })


      return NextResponse.json({
        id: result?.chat_session_id,
        name: "server session",
        created_at: result?.created_at,
        modified_at: result?.modified_at
      });

    } catch (error: any) {
      console.error(JSON.stringify(error?.response?.data, null, 2));
      return new NextResponse(error, { status: error.response?.status || 500 });
    }
  }

  return NextResponse.json({
    id: randomUUID(),
    name: body?.prompt || "local session",
    created_at: new Date().toISOString(),
    modified_at: new Date().toISOString()
  });
}