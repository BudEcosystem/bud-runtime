import { tempApiBaseUrl } from "@/components/environment";
import { Worker } from "cluster";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { IEndPoint } from "src/hooks/useEndPoint";


export type StepOneForm = {
    name: string;
    tags: [];
    description: string;
    routing_strategy: [] | {};
};

export type Endpoints = {
    endpoint_id: string,
    fallback_endpoint_ids?: [],
    tpm?: number,
    rpm?: number,
    weight?: number,
    cool_down_period?: number
};

// create zustand store
export const useRoutes = create<{
    selectedProjectId: string;
    stepOneData: StepOneForm | null;
    stepTwoData: Endpoints[] | null;
    strategy: string,

    endpoints: IEndPoint[],
    multiSelectedEndpoints: IEndPoint[],
    setEndpoints: (endpoint: IEndPoint[]) => void;
    setMultiSelectedEndpoints: (endpoint: IEndPoint) => void;
    setSelecteUnselectAllEndpoints: (selectAll: boolean) => void;


    setStrategy: (data: string) => void;
    setStepOneData: (data: StepOneForm) => void;
    setStepTwoData: () => void;
    setSelectedProjectId: (data: string) => void;


    createRoute: () => Promise<any>;



}>((set, get) => ({
    selectedProjectId: null,
    strategy: null,
    stepOneData: null,
    stepTwoData: null,

    endpoints: [],
    multiSelectedEndpoints: [],
    setMultiSelectedEndpoints: (endpoint) => {
        set((state) => {
            const isAlreadySelected = state.multiSelectedEndpoints.some(
                (selected) => selected.id === endpoint.id
            );

            return {
                multiSelectedEndpoints: isAlreadySelected
                    ? state.multiSelectedEndpoints.filter((selected) => selected.id !== endpoint.id)
                    : [...state.multiSelectedEndpoints, endpoint],
            };
        });
    },

    setEndpoints: (endpoint) => {
        set({ endpoints: endpoint });
    },

    setSelecteUnselectAllEndpoints: (selectAll) => {
        if (selectAll) {
            set({ multiSelectedEndpoints: [] });
        } else {
            const nodes = get().endpoints;
            set({ multiSelectedEndpoints: nodes });
        }
    },

    setStrategy: (data) => {
        set({ strategy: data });
    },

    setStepOneData: (data) => {
        set({ stepOneData: data });
    },

    setStepTwoData: () => {
        const endpoints = get().multiSelectedEndpoints;
        const stepTwoFormatted: Endpoints[] = endpoints.map((ep) => ({
            endpoint_id: ep.id,
            fallback_endpoint_ids: [],
            tpm: 0,
            rpm: 0,
            weight: 0,
            cool_down_period: 0,
        }));

        set({ stepTwoData: stepTwoFormatted });
    },


    setSelectedProjectId: (data) => {
        set({ selectedProjectId: data });
    },

    createRoute: async () => {
        const projectId = get().selectedProjectId;
        const payload = {
            project_id: projectId,
            name: get().stepOneData?.name,
            description: get().stepOneData?.description,
            tags: get().stepOneData?.tags,
            routing_strategy: get().stepOneData?.routing_strategy,
            endpoints: get().stepTwoData,
        };

        const response = await AppRequest.Post(
            `${tempApiBaseUrl}/routers/`,
            payload,
            {
                headers: {
                    "x-resource-type": "project",
                    "x-entity-id": projectId,
                },
            }
        );

        console.log(response);
        return response;
    },

}));
