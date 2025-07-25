import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

export const useCloudCredentials = create<{
  setSelectedProvider: (provider: any) => void;
  selectedProvider: any;
  addCloudCredential: (credential: any) => Promise<any>;
  selectedCredential: any;
  setSelectedCredential: (credential: any) => void;
}>((set) => ({
  selectedCredential: null,
  setSelectedCredential: (credential: any) => {
    set({ selectedCredential: credential });
  },
  setSelectedProvider: (provider: any) => {
    const schemaDefinition = JSON.parse(provider.schema_definition);
    provider.jsonSchema = schemaDefinition;

    set({ selectedProvider: provider });
  },
  selectedProvider: null,
  addCloudCredential: async (credential: any) => {
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/credentials/cloud-providers`,
        credential,
      );

      if (response.status === 201) {
        // Reset the form fields
        //set({ selectedProvider: null });
        return response.data;
      }
      return false;
    } catch (error) {
      console.error("Error adding cloud credential:", error);
      return false;
    }
  },
}));
