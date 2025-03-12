import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function GET(req: Request, res: Response) {
  console.log('GET /api/sessions');
  const authorization = req.headers.get('authorization');
  if(!authorization) {
    return NextResponse.json([]);
  }

  const result = await axios
    .get(`${tempApiBaseUrl}/playground/chat-sessions`, {
      headers: {
        authorization: authorization,
      },
    })
    .then((response) => {
      return response.data.chat_sessions;
    })
    .catch((err) => {
      console.error(err.response);
      return []
    })

  console.log('result', result);

  return NextResponse.json(result);
}
