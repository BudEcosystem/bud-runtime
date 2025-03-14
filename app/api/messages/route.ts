import { tempApiBaseUrl } from '@/app/components/bud/environment';
import { NEW_SESSION } from '@/app/components/bud/hooks/useMessages';
import axios from 'axios';
import { randomUUID } from 'crypto';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();
  const authorization = req.headers.get('authorization');
  const apiKey = req.headers.get('api-key');

  if (authorization) {
    try {
      const result = await axios
        .post(`${tempApiBaseUrl}/playground/messages`,
          body, {
          headers: {
            authorization: authorization,
            'api-key': apiKey,
          },
        })
        .then((response) => {
          return response.data;
        })

      return NextResponse.json(result);

    } catch (error: any) {
      return new NextResponse(error, { status: error.response?.status || 500 });
    }
  }
  return NextResponse.json({
    ...body,
    id: body.id || randomUUID(),
  });
}
