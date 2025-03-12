import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function GET(req: Request) {
  console.log('GET /api/sessions');
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  try {

    const result = await axios
      .get(`${tempApiBaseUrl}/playground/chat-sessions`, {
        headers: {
          authorization: authorization,
          'api-key': apiKey,
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
