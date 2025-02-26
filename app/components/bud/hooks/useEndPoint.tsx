import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext } from "react";
import ChatContext from "@/app/context/ChatContext";

export function useEndPoints() {
  const { chat, endpoints, setEndpoints } = useContext(ChatContext);

  async function getEndPoints({ page = 1, limit = 25 }) {
    try {
      const result = await axios
        .get(`${tempApiBaseUrl}/playground/deployments`, {
          params: {
            page: page,
            limit: limit,
          },
          headers: {
            "api-key": chat?.apiKey,
          },
        })
        .then((res) => {
          console.log(res.data.endpoints);
          setEndpoints(res.data.endpoints);
          return res.data.endpoints;
        });

      console.log(result);
      return result;
    } catch (error) {
      return error;
    }
  }

  return { getEndPoints, endpoints };
}
