import { tempApiBaseUrl } from "../environment";
import axios from "axios";
import { useContext } from "react";
import ChatContext from "@/app/context/ChatContext";

function successToast(message: string) {
  console.log(message);
}

export function useEndPoints() {
  const { apiKey, endpoints } = useContext(ChatContext);

  async function getEndPoints({ page = 1, limit = 25 }) {
    const result = await axios
      .get(`${tempApiBaseUrl}/playground/deployments`, {
        params: {
          page: page,
          limit: limit,
        },
        headers: {
          "api-key": apiKey,
        },
      })
      .then((res) => {
        console.log(res.data.endpoints);
        return res.data.endpoints;
      });

    console.log(result);
    return result;
  }

  return { getEndPoints, endpoints };
}
