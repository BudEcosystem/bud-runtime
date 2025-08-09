import { useState } from "react";

export interface Provider {
  id: string;
  name: string;
  type: string;
}

export const useCloudProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const getProviders = async () => {
    setIsLoading(true);
    try {
      // TODO: Implement actual API call
      setProviders([]);
    } catch (error) {
      console.error("Error fetching providers:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return {
    providers,
    isLoading,
    getProviders,
  };
};
