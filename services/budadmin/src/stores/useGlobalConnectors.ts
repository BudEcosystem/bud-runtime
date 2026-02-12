import { create } from "zustand";
import { GlobalConnectorService } from "@/services/globalConnectorService";
import { errorToast, successToast } from "@/components/toast";

export interface Gateway {
  id: string;
  name: string;
  url?: string;
  transport?: string;
  visibility?: string;
  auth_type?: string;
  slug?: string;
  tags?: string[];
  enabled?: boolean;
  tools?: any[];
  oauth_status?: {
    oauth_enabled?: boolean;
    grant_type?: string;
    message?: string;
  };
}

export interface ConfiguredConnector {
  id: string;
  gateway_id: string;
  connector_id: string;
  name: string;
  enabled: boolean;
  tags: string[];
  icon?: string;
  description?: string;
  category?: string;
  auth_type?: string;
  documentation_url?: string;
  tool_count: number;
  oauth_connected: boolean;
}

export interface RegistryConnector {
  id: string;
  name: string;
  icon?: string;
  category?: string;
  tags?: string[];
  url: string;
  provider: string;
  description?: string;
  documentation_url?: string;
  auth_type?: string;
  credential_schema?: any[];
}

interface GlobalConnectorsState {
  // ─── Admin: Registry ───────────────────────────────────────────────
  registryConnectors: RegistryConnector[];
  registryTotal: number;
  registryLoading: boolean;

  // ─── Admin: Gateways ──────────────────────────────────────────────
  gateways: Gateway[];
  gatewaysTotal: number;
  gatewaysLoading: boolean;

  // ─── Admin: Configured ────────────────────────────────────────────
  configuredConnectors: ConfiguredConnector[];
  configuredTotal: number;
  configuredLoading: boolean;

  // ─── User: Available ──────────────────────────────────────────────
  availableGateways: Gateway[];
  availableTotal: number;
  availableLoading: boolean;

  // ─── Actions ──────────────────────────────────────────────────────
  fetchRegistry: (params?: { name?: string; page?: number; limit?: number }, append?: boolean) => Promise<void>;
  fetchRegistryConnector: (connectorId: string) => Promise<RegistryConnector | null>;
  configureConnector: (connectorId: string, credentials: Record<string, any>) => Promise<boolean>;
  fetchGateways: (params?: { page?: number; limit?: number }) => Promise<void>;
  getGateway: (gatewayId: string) => Promise<Gateway | null>;
  deleteGateway: (gatewayId: string) => Promise<boolean>;
  fetchConfigured: (params?: { client?: string; include_disabled?: boolean; page?: number; limit?: number }) => Promise<void>;
  toggleConnector: (gatewayId: string, enabled: boolean) => Promise<boolean>;
  updateClients: (gatewayId: string, clients: string[]) => Promise<boolean>;
  fetchAvailable: (params?: { page?: number; limit?: number }) => Promise<void>;
  initiateOAuth: (gatewayId: string) => Promise<any>;
  handleOAuthCallback: (code: string, state: string) => Promise<any>;
  getOAuthStatus: (gatewayId: string) => Promise<any>;
  fetchToolsForGateway: (gatewayId: string) => Promise<any>;
  listToolsForGateway: (gatewayId: string) => Promise<any[]>;
}

export const useGlobalConnectors = create<GlobalConnectorsState>((set) => ({
  registryConnectors: [],
  registryTotal: 0,
  registryLoading: false,

  gateways: [],
  gatewaysTotal: 0,
  gatewaysLoading: false,

  configuredConnectors: [],
  configuredTotal: 0,
  configuredLoading: false,

  availableGateways: [],
  availableTotal: 0,
  availableLoading: false,

  fetchRegistry: async (params, append = false) => {
    set({ registryLoading: !append });
    try {
      const res = await GlobalConnectorService.listRegistry(params);
      const data = res?.data;
      if (data?.success) {
        set((state) => ({
          registryConnectors: append
            ? [...state.registryConnectors, ...(data.connectors || [])]
            : data.connectors || [],
          registryTotal: data.total_record || 0,
        }));
      }
    } catch (e) {
      errorToast("Failed to load registry connectors");
    } finally {
      set({ registryLoading: false });
    }
  },

  fetchRegistryConnector: async (connectorId) => {
    try {
      const res = await GlobalConnectorService.getRegistryConnector(connectorId);
      return res?.data?.connector || null;
    } catch (e) {
      errorToast("Failed to load connector details");
      return null;
    }
  },

  configureConnector: async (connectorId, credentials) => {
    try {
      const res = await GlobalConnectorService.configureConnector({
        connector_id: connectorId,
        credentials,
      });
      if (res?.data?.success) {
        successToast("Connector configured successfully");
        return true;
      }
      errorToast(res?.data?.message || "Failed to configure connector");
      return false;
    } catch (e: any) {
      errorToast(e?.response?.data?.message || "Failed to configure connector");
      return false;
    }
  },

  fetchGateways: async (params) => {
    set({ gatewaysLoading: true });
    try {
      const res = await GlobalConnectorService.listGateways(params);
      const data = res?.data;
      if (data?.success) {
        set({
          gateways: data.gateways || [],
          gatewaysTotal: data.total_record || 0,
        });
      }
    } catch (e) {
      errorToast("Failed to load gateways");
    } finally {
      set({ gatewaysLoading: false });
    }
  },

  getGateway: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.getGateway(gatewayId);
      return res?.data?.gateway || null;
    } catch (e) {
      errorToast("Failed to load gateway details");
      return null;
    }
  },

  deleteGateway: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.deleteGateway(gatewayId);
      if (res?.data?.success) {
        successToast("Gateway deleted successfully");
        set((state) => ({
          gateways: state.gateways.filter((g) => g.id !== gatewayId),
          gatewaysTotal: state.gatewaysTotal - 1,
        }));
        return true;
      }
      errorToast(res?.data?.message || "Failed to delete gateway");
      return false;
    } catch (e: any) {
      errorToast(e?.response?.data?.message || "Failed to delete gateway");
      return false;
    }
  },

  fetchConfigured: async (params) => {
    set({ configuredLoading: true });
    try {
      const res = await GlobalConnectorService.listConfigured(params);
      const data = res?.data;
      if (data?.success) {
        set({
          configuredConnectors: data.connectors || [],
          configuredTotal: data.total_record || 0,
        });
      }
    } catch (e) {
      errorToast("Failed to load configured connectors");
    } finally {
      set({ configuredLoading: false });
    }
  },

  toggleConnector: async (gatewayId, enabled) => {
    try {
      const res = await GlobalConnectorService.toggleConnector(gatewayId, enabled);
      if (res?.data?.success) {
        successToast(`Connector ${enabled ? "enabled" : "disabled"} successfully`);
        set((state) => ({
          configuredConnectors: state.configuredConnectors.map((c) =>
            c.gateway_id === gatewayId ? { ...c, enabled } : c
          ),
        }));
        return true;
      }
      errorToast(res?.data?.message || "Failed to toggle connector");
      return false;
    } catch (e: any) {
      errorToast(e?.response?.data?.message || "Failed to toggle connector");
      return false;
    }
  },

  updateClients: async (gatewayId, clients) => {
    try {
      const res = await GlobalConnectorService.updateClients(gatewayId, clients);
      if (res?.data?.success) {
        successToast("Client access updated successfully");
        // Update tags in local state
        set((state) => ({
          configuredConnectors: state.configuredConnectors.map((c) => {
            if (c.gateway_id !== gatewayId) return c;
            const nonClientTags = c.tags.filter((t) => !t.startsWith("client:"));
            return { ...c, tags: [...nonClientTags, ...clients.map((cl) => `client:${cl}`)] };
          }),
        }));
        return true;
      }
      errorToast(res?.data?.message || "Failed to update client access");
      return false;
    } catch (e: any) {
      errorToast(e?.response?.data?.message || "Failed to update client access");
      return false;
    }
  },

  fetchAvailable: async (params) => {
    set({ availableLoading: true });
    try {
      const res = await GlobalConnectorService.listAvailable(params);
      const data = res?.data;
      if (data?.success) {
        set({
          availableGateways: data.gateways || [],
          availableTotal: data.total_record || 0,
        });
      }
    } catch (e) {
      errorToast("Failed to load available connectors");
    } finally {
      set({ availableLoading: false });
    }
  },

  initiateOAuth: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.initiateOAuth(gatewayId);
      return res?.data;
    } catch (e) {
      errorToast("Failed to initiate OAuth");
      return null;
    }
  },

  handleOAuthCallback: async (code, state) => {
    try {
      const res = await GlobalConnectorService.handleOAuthCallback({ code, state });
      return res?.data;
    } catch (e) {
      errorToast("Failed to complete OAuth");
      return null;
    }
  },

  getOAuthStatus: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.getOAuthStatus(gatewayId);
      return res?.data;
    } catch (e) {
      return null;
    }
  },

  fetchToolsForGateway: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.fetchTools(gatewayId);
      return res?.data;
    } catch (e) {
      errorToast("Failed to fetch tools");
      return null;
    }
  },

  listToolsForGateway: async (gatewayId) => {
    try {
      const res = await GlobalConnectorService.listTools(gatewayId);
      return res?.data?.tools || [];
    } catch (e) {
      errorToast("Failed to list tools");
      return [];
    }
  },
}));
