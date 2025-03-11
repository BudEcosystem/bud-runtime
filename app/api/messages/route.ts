import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function POST(req: Request, res: Response) {
  const body = await req.json();
  const authorization = req.headers.get('authorization');
  const result = await axios
    .post(`${tempApiBaseUrl}/playground/messages`,
      body, {
      headers: {
        authorization: authorization,
      },
    })
    .then((response) => {
      return response.data.chat_sessions;
    })
    .catch(() => {
      return []
    })

  return NextResponse.json(result);
}
