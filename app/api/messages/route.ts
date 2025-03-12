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
      return response.data;
    })
    .catch((err) => {
      console.error(err.response);
      return err?.response?.data;
    })

  return NextResponse.json(result);
}
