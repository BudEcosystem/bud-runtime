import { create } from 'zustand';

function successToast(message: string) {
  console.log(message);
}

export type Endpoint = {
  "id": string,
  "name": string,
  "status": string,
  "deployment_config": {
    "avg_context_length": number
    "avg_sequence_length": number,
    "concurrent_requests": number
  },
  "created_at": string,
  "modified_at": string,
}

export const useEndPoints = create<
  {
    pageSource: string;
    getEndPoints: ({
      id,
      page,
      limit,
      name,
    }: {
      id: any;
      page: any;
      limit: any;
      name?: string;
      order_by?: string;
    }) => void;
  }
>((set, get) => ({
  pageSource: '',
  clusterDetails: undefined,
  endPoints: [],
  getEndPoints: async ({
    id,
    page,
    limit,
    name,
    order_by = "-created_at",
  }) => {
    
  },
}));