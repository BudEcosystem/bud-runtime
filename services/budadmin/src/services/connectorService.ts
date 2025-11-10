import { tempApiBaseUrl } from '@/components/environment';
import { AppRequest } from 'src/pages/api/requests';

/**
 * Service for handling connector-related API calls
 */

interface RegisterConnectorPayload {
  credentials: Record<string, any>;
  version: number;
}

interface OAuthInitiatePayload {
  prompt_id: string;
  connector_id: string;
  version?: number;
}

interface ConnectToolsPayload {
  prompt_id: string;
  connector_id: string;
  tool_ids: string[];
  version: number;
}

interface FetchToolsParams {
  prompt_id: string;
  connector_id: string;
  page?: number;
  limit?: number;
}

export class ConnectorService {
  /**
   * Initiate OAuth flow for a connector
   */
  static async initiateOAuth(payload: OAuthInitiatePayload) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/prompts/oauth/initiate`,
      payload
    );
  }

  /**
   * Check OAuth status for a connector
   */
  static async checkOAuthStatus(promptId: string, connectorId: string) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/prompts/oauth/status`,
      {
        params: {
          prompt_id: promptId,
          connector_id: connectorId
        }
      }
    );
  }

  /**
   * Complete OAuth callback with authorization code
   */
  static async completeOAuthCallback(promptId: string, connectorId: string, code: string, state: string) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/prompts/oauth/callback`,
      {
        prompt_id: promptId,
        connector_id: connectorId,
        code,
        state
      }
    );
  }

  /**
   * Register a connector with credentials
   */
  static async registerConnector(
    promptId: string,
    connectorId: string,
    payload: RegisterConnectorPayload
  ) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/prompts/${promptId}/connectors/${connectorId}/register`,
      payload
    );
  }

  /**
   * Fetch connector details by ID
   */
  static async fetchConnectorDetails(connectorId: string) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/prompts/connectors/${connectorId}`
    );
  }

  /**
   * Fetch tools for a connector
   */
  static async fetchTools(params: FetchToolsParams) {
    return await AppRequest.Get(`${tempApiBaseUrl}/prompts/tools`, {
      params: {
        prompt_id: params.prompt_id,
        connector_id: params.connector_id,
        page: params.page || 1,
        limit: params.limit || 100,
      }
    });
  }

  /**
   * Connect tools to a prompt
   */
  static async connectTools(payload: ConnectToolsPayload) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/prompts/prompt-config/add-tool`,
      payload
    );
  }

  /**
   * Disconnect a connector from a prompt
   */
  static async disconnectConnector(promptId: string, connectorId: string) {
    return await AppRequest.Delete(
      `${tempApiBaseUrl}/prompts/${promptId}/connectors/${connectorId}/disconnect`
    );
  }
}
