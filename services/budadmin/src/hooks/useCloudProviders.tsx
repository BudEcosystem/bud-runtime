import { tempApiBaseUrl } from "@/components/environment";
import { errorToast } from "@/components/toast";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

export type Provider = {
  id: string;
  name: string;
  icon: string;
  description: string;
  type: string;
};

let dummyProviders: Provider[] = [
  {
    id: "1",
    name: "Amazon Web Services",
    icon: "/images/drawer/zephyr.png",
    description: "Amazon Web Services",
    type: "cloud",
  },
  {
    id: "2",
    name: "Google Cloud Platform",
    icon: "/images/drawer/zephyr.png",
    description: "Google Cloud Platform",
    type: "cloud",
  },
  {
    id: "3",
    name: "Microsoft Azure",
    icon: "/images/drawer/zephyr.png",
    description: "Microsoft Azure",
    type: "cloud",
  },
  {
    id: "4",
    name: "IBM Cloud",
    icon: "/images/drawer/zephyr.png",
    description: "IBM Cloud",
    type: "cloud",
  },
  {
    id: "5",
    name: "Oracle Cloud",
    icon: "/images/drawer/zephyr.png",
    description: "Oracle Cloud",
    type: "cloud",
  },
  {
    id: "6",
    name: "Digital Ocean",
    icon: "/images/drawer/zephyr.png",
    description: "Digital Ocean",
    type: "cloud",
  },
  {
    id: "7",
    name: "Linode",
    icon: "/images/drawer/zephyr.png",
    description: "Linode",
    type: "cloud",
  },
];

// create zustand store
export const useCloudProviders = create<{
  providers: Provider[];
  loading: boolean;
  getProviders: (page: any, limit: any, search?: string, capabilities?: string) => void;
}>((set) => ({
  providers: [],
  loading: true,
  getProviders: async (page: any, limit: any, search?: string, capabilities?: string) => {
    const params: Record<string, any> = {
      page,
      limit,
      search: Boolean(search),
      order_by: "-created_at",
      capabilities: capabilities || "model", // Use provided capabilities or default to "model"
    };

    if (search) {
      params.name = search;
    }
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/models/providers`, {
        params,
      });
      const listData = response.data.providers;
      const updatedListData = listData.map((item) => {
        return {
          ...item,
        };
      });

      set({ providers: updatedListData });
    } catch (error) {
      // set({ providers: dummyProviders });
      console.error("Error creating model:", error);
      errorToast("Unable to fetch providers");
    } finally {
      set({ loading: false });
    }
  },
}));
