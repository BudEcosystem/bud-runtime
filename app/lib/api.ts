import { AppRequest } from "@/app/api/requests";


export const getEndpoints = async (page = 1, limit = 25, apiKey = "") => {
    const headers: any = {
        'Content-Type': 'application/json'
      };
      if (apiKey) {
        headers["api-key"] = apiKey;
      }
      try {
        const result = await AppRequest.Post(`api/deployments`, {
          page: page,
          limit: limit,
          search: false,
        }, {}, headers).then((res) => {
          return res.data;
        });
        return result;
      } catch (error) {
        return error;
      }
}