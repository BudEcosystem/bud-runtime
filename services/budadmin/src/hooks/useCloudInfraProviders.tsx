// dashboard/src/hooks/useCloudInfraProviders.tsx
import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

/**
 * Represents a cloud infrastructure provider
 */
export type CloudInfraProvider = {
  /** Unique identifier for the provider */
  id: string;
  /** Display name of the provider */
  name: string;
  /** Description of the provider services */
  description: string;
  /** URL to the provider's logo image */
  logo_url: string;
  /** JSON schema definition for the provider configuration */
  schema_definition: string;
  /** Whether the provider is currently enabled */
  is_enabled: boolean;
  /** Alternative unique identifier */
  unique_id: string;
  /** Creation timestamp */
  created_at: string;
  /** Last modification timestamp */
  modified_at: string;
};

export type CloudCredentials = {
  /** Unique identifier for the credentials */
  id: string;
  /** ID of the cloud provider these credentials are for */
  provider_id: string;
  /** Name of the cloud provider */
  provider_name: string;
  /** When the credentials were created */
  created_at: string;
  /** Summary of the credential details with sensitive information masked */
  credential_summary: Record<string, string>;
  /** The credential name */
  credential_name: string;
};

export type CloudCredentialFilter = {
  providerId?: string | null;
};

/**
 * State for cloud infrastructure providers
 */
export type CloudInfraProvidersState = {
  /** List of available cloud providers */
  providers: CloudInfraProvider[];
  /** List of saved credentials for each provider **/
  credentials: CloudCredentials[];
  /** Loading state indicator */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Function to fetch providers from the API */
  getProviders: () => Promise<void>;
  /** Get Saved Credentials for user */
  getCloudCredentials: (filter?: CloudCredentialFilter) => Promise<void>;
  /** Refresh both providers and credentials data */
  refreshCloudCredentials: (filter?: CloudCredentialFilter) => Promise<void>;
  /** Region By Provider **/
  getRegionByProviderID: (providerID: string) => Promise<any>;
};

/**
 * Zustand store for managing cloud infrastructure providers
 */
export const useCloudInfraProviders = create<CloudInfraProvidersState>(
  (set) => ({
    getRegionByProviderID: async (providerID: string) => {
      try {
        set({ isLoading: true });
        const response: any = await AppRequest.Get(
          `${tempApiBaseUrl}/credentials/cloud-providers/${providerID}/regions`,
        );
        set({ isLoading: false });
        return response.data.regions;
      } catch (error) {
        set({ isLoading: false });
        console.error("error", error);
        return error;
      }
    },
    providers: [],
    credentials: [],
    isLoading: false,
    error: null,
    getProviders: async () => {
      try {
        set({ isLoading: true, error: null });
        const response = await AppRequest.Get(
          `${tempApiBaseUrl}/credentials/cloud-providers`,
        );
        set({ providers: response.data.providers, isLoading: false, error: null });
      } catch (error) {
        console.error(error);
        set({ error: error.message, isLoading: false });
      }
    },
    getCloudCredentials: async (filter?: CloudCredentialFilter) => {
      try {
        set({ isLoading: true, error: null });
        let url = `${tempApiBaseUrl}/credentials/cloud-providers/credentials`;
        if (filter) {
          const params = new URLSearchParams();
          if (filter.providerId) {
            params.append("provider_id", filter.providerId);
          }
          const queryString = params.toString();
          if (queryString) {
            url += `?${queryString}`;
          }
        }
        const response = await AppRequest.Get(url);
        set({ credentials: response.data.credentials, isLoading: false, error: null });
      } catch (error) {
        console.error(error);
        set({ error: error.message, isLoading: false });
      }
    },
    refreshCloudCredentials: async (filter?: CloudCredentialFilter) => {
      set({ isLoading: true, error: null });

      // Fetch providers - handle errors independently
      const providersPromise = AppRequest.Get(
        `${tempApiBaseUrl}/credentials/cloud-providers`,
      )
        .then((response) => {
          set((state) => ({
            ...state,
            providers: response.data.providers,
          }));
          return { success: true as const, error: undefined };
        })
        .catch((error) => {
          console.error("Error fetching providers:", error);
          return { success: false as const, error };
        });

      // Fetch credentials - handle errors independently
      const credentialsPromise = (async () => {
        let url = `${tempApiBaseUrl}/credentials/cloud-providers/credentials`;
        if (filter) {
          const params = new URLSearchParams();
          if (filter.providerId) {
            params.append("provider_id", filter.providerId);
          }
          const queryString = params.toString();
          if (queryString) {
            url += `?${queryString}`;
          }
        }
        return AppRequest.Get(url)
          .then((response) => {
            set((state) => ({
              ...state,
              credentials: response.data.credentials,
            }));
            return { success: true as const, error: undefined };
          })
          .catch((error) => {
            console.error("Error fetching credentials:", error);
            return { success: false as const, error };
          });
      })();

      // Wait for both to complete, but don't fail if one fails
      const [providersResult, credentialsResult] = await Promise.all([
        providersPromise,
        credentialsPromise,
      ]);

      // Only set error if providers failed (credentials failing is less critical)
      if (!providersResult.success) {
        set({
          error: providersResult.error?.message || "Failed to load providers",
          isLoading: false,
        });
      } else {
        set({ isLoading: false, error: null });
      }
    },
  }),
);
