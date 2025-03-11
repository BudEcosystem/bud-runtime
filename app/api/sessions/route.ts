import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function GET(req: Request, res: Response) {
  const authorization = req.headers.get('authorization');
  const result = await axios
    .get(`${tempApiBaseUrl}/playground/chat-sessions`, {
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
