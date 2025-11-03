import { AppRequest } from "@/app/api/requests";

// Helper function to check if a string looks like a JWT
const isJWT = (token: string): boolean => {
  if (!token) return false;
  const parts = token.split('.');
  return parts.length === 3;
};

export const getEndpoints = async (page = 1, limit = 25, apiKey = "", accessKey = "") => {
    const headers: any = {
        'Content-Type': 'application/json'
      };

      // Check if accessKey is a JWT token
      if (accessKey && isJWT(accessKey)) {
        // Use access_key as Bearer token if it's a JWT
        headers["Authorization"] = `Bearer ${accessKey}`;
      } else {
        // Regular API key authentication
        if (apiKey) {
          headers["api-key"] = apiKey;
        }
        if (accessKey) {
          headers["access-key"] = accessKey;
        }
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

export const getPromptConfig = async (promptId: string, apiKey = "", accessKey = "") => {
  const headers: any = {
    'Content-Type': 'application/json'
  };

  // Check if accessKey is a JWT token
  if (accessKey && isJWT(accessKey)) {
    // Use access_key as Bearer token if it's a JWT
    headers["Authorization"] = `Bearer ${accessKey}`;
  } else {
    // Regular API key authentication
    if (apiKey) {
      headers["api-key"] = apiKey;
    }
    if (accessKey) {
      headers["access-key"] = accessKey;
    }
  }

  try {
    const result = await AppRequest.Get(`api/prompts/${promptId}`, {
      headers
    }).then((res) => {
      return res.data;
    });
    return result;
  } catch (error) {
    console.error(`Failed to fetch prompt config for ${promptId}:`, error);
    return null;
  }
}

export interface PromptChatRequest {
  prompt: {
    id: string;
    version?: string;
    variables?: Record<string, string>;
  };
  input?: string;
  model?: string;
  metadata?: {
    project_id?: string;
    base_url?: string;
  };
  settings?: {
    temperature?: number;
  };
}

export const sendPromptChat = async (
  request: PromptChatRequest,
  apiKey = "",
  accessKey = ""
) => {
  const headers: any = {
    'Content-Type': 'application/json'
  };

  // Check if accessKey is a JWT token
  if (accessKey && isJWT(accessKey)) {
    // Use access_key as Bearer token if it's a JWT
    headers["Authorization"] = `Bearer ${accessKey}`;
  } else {
    // Regular API key authentication
    if (apiKey) {
      headers["api-key"] = apiKey;
    }
    if (accessKey) {
      headers["access-key"] = accessKey;
    }
  }

  try {
    const result = await AppRequest.Post(
      `api/prompt-chat`,
      request,
      {},
      headers
    ).then((res) => {
      return res.data;
    });
    return result;
  } catch (error) {
    console.error(`Failed to send prompt chat:`, error);
    throw error;
  }
}
