import { tempApiBaseUrl } from '@/app/components/bud/environment';
import axios from 'axios';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  console.log('POST /api/deployments');

  const body = await req.json();
  const authorization = req.headers.get('authorization');
  if (!authorization) {
    return NextResponse.json([]);
  }
  try {
    const result = await axios
      .get(`${tempApiBaseUrl}/playground/deployments`, {
        params: {
          page: body.page,
          limit: body.limit,
          search: false,
        },
        headers: {
          authorization: authorization,
        },
      })
      .then((response) => {
        return response.data.endpoints;
      })
    return NextResponse.json(result);
  } catch (error: any) {
    return new NextResponse(error, { status: error.response?.status || 500 });
  }
}
