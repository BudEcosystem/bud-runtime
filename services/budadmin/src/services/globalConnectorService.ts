import { tempApiBaseUrl } from '@/components/environment';
import { AppRequest } from 'src/pages/api/requests';

/**
 * Service for global connector operations (admin + user).
 * Proxies through budapp to MCP Foundry.
 */

// ─── Admin: Registry ─────────────────────────────────────────────────────────

export interface RegistryListParams {
  name?: string;
  page?: number;
  limit?: number;
}

export interface ConfigureConnectorPayload {
  connector_id: string;
  credentials: Record<string, any>;
}

// ─── Admin: Configured Connectors ────────────────────────────────────────────

export interface ConfiguredListParams {
  client?: string;
  include_disabled?: boolean;
  page?: number;
  limit?: number;
}

// ─── Admin: Gateways ─────────────────────────────────────────────────────────

export interface GatewayListParams {
  page?: number;
  limit?: number;
}

// ─── User: OAuth ─────────────────────────────────────────────────────────────

export interface OAuthCallbackPayload {
  code: string;
  state: string;
}

export class GlobalConnectorService {
  // ═══ Admin: Registry ═══════════════════════════════════════════════════════

  /** Browse connectors from MCP Foundry registry */
  static async listRegistry(params?: RegistryListParams) {
    return await AppRequest.Get(`${tempApiBaseUrl}/connectors/registry`, {
      params: {
        page: params?.page || 1,
        limit: params?.limit || 20,
        ...(params?.name ? { name: params.name } : {}),
      },
    });
  }

  /** Get a single connector from the registry */
  static async getRegistryConnector(connectorId: string) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/connectors/registry/${connectorId}`
    );
  }

  // ═══ Admin: Configured Connectors ════════════════════════════════════════

  /** List configured connectors enriched with registry metadata */
  static async listConfigured(params?: ConfiguredListParams) {
    return await AppRequest.Get(`${tempApiBaseUrl}/connectors/configured`, {
      params: {
        page: params?.page || 1,
        limit: params?.limit || 100,
        ...(params?.client ? { client: params.client } : {}),
        ...(params?.include_disabled ? { include_disabled: true } : {}),
      },
    });
  }

  /** Enable or disable a configured connector gateway */
  static async toggleConnector(gatewayId: string, enabled: boolean) {
    return await AppRequest.Patch(
      `${tempApiBaseUrl}/connectors/configured/${gatewayId}/toggle`,
      { enabled }
    );
  }

  /** Update which clients can access a configured connector gateway */
  static async updateClients(gatewayId: string, clients: string[]) {
    return await AppRequest.Patch(
      `${tempApiBaseUrl}/connectors/configured/${gatewayId}/clients`,
      { clients }
    );
  }

  /** Backfill tags on an existing gateway */
  static async tagExistingGateway(gatewayId: string, connectorId: string) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/connectors/configured/${gatewayId}/tag`,
      { connector_id: connectorId }
    );
  }

  // ═══ Admin: Gateway CRUD ═══════════════════════════════════════════════════

  /** Configure a global connector (create gateway with credentials) */
  static async configureConnector(payload: ConfigureConnectorPayload) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/connectors/gateways`,
      payload
    );
  }

  /** List all global gateways (admin) */
  static async listGateways(params?: GatewayListParams) {
    return await AppRequest.Get(`${tempApiBaseUrl}/connectors/gateways`, {
      params: {
        page: params?.page || 1,
        limit: params?.limit || 20,
      },
    });
  }

  /** Get gateway details with tools */
  static async getGateway(gatewayId: string) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/connectors/gateways/${gatewayId}`
    );
  }

  /** Update a gateway */
  static async updateGateway(
    gatewayId: string,
    updateData: Record<string, any>
  ) {
    return await AppRequest.Put(
      `${tempApiBaseUrl}/connectors/gateways/${gatewayId}`,
      updateData
    );
  }

  /** Delete a gateway */
  static async deleteGateway(gatewayId: string) {
    return await AppRequest.Delete(
      `${tempApiBaseUrl}/connectors/gateways/${gatewayId}`
    );
  }

  // ═══ User: Available Connectors ════════════════════════════════════════════

  /** List gateways available for current user with OAuth status */
  static async listAvailable(params?: GatewayListParams) {
    return await AppRequest.Get(`${tempApiBaseUrl}/connectors/available`, {
      params: {
        page: params?.page || 1,
        limit: params?.limit || 20,
      },
    });
  }

  // ═══ User: OAuth ══════════════════════════════════════════════════════════

  /** Start OAuth flow for a gateway */
  static async initiateOAuth(gatewayId: string) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/connectors/${gatewayId}/oauth/initiate`,
      {}
    );
  }

  /** Handle OAuth callback */
  static async handleOAuthCallback(payload: OAuthCallbackPayload) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/connectors/oauth/callback`,
      payload
    );
  }

  /** Get OAuth status for a gateway */
  static async getOAuthStatus(gatewayId: string) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/connectors/${gatewayId}/oauth/status`
    );
  }

  // ═══ User: Tools ══════════════════════════════════════════════════════════

  /** Fetch tools after OAuth completion */
  static async fetchTools(gatewayId: string) {
    return await AppRequest.Post(
      `${tempApiBaseUrl}/connectors/${gatewayId}/fetch-tools`,
      {}
    );
  }

  /** List tools from a gateway */
  static async listTools(gatewayId: string, page = 1, limit = 100) {
    return await AppRequest.Get(
      `${tempApiBaseUrl}/connectors/${gatewayId}/tools`,
      {
        params: { page, limit },
      }
    );
  }
}
