import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { Provider } from "./useCloudProviders";
import { Model } from "./useModels";
import { Cluster } from "./useCluster";

type GetsimulationParams = {
    page: number;
    limit: number;
    order_by?: string;
    name?: string;
    email?: string;
    role?: string;
    status?: string;
};
export type Simulation = {
    key?: string;
    created_at?: string;
    model: [],
    cluster: [],
    name?: string,
    modelName?: string;
    modelImage?: string;
    clusterName?: string;
    clusterImage?: string;
    node_type?: any;
    vendor_type?: string;
    status?: string;
    concurrentRequest?: string;
    tpot?: string;
    ttft?: string;
    id?: string;
};

export type ModelClusterDetails = {
    cluster?: Cluster;
    deployment_config?: any;
    id: string,
    model: Model,
    name?: string,
    status?: string;
};
export type SimulationResult = {
    output_throughput: number;
    median_ttft_ms: number;
    median_tpot_ms: number;
    median_itl_ms: number;
    median_e2el_ms: number;
    p25_ttft_ms: number;
    p25_throughput: number;
    p25_tpot_ms: number;
    p25_itl_ms: number;
    p25_e2el_ms: number;
    modified_at: string;
    p75_throughput: number;
    p75_ttft_ms: number;
    p75_tpot_ms: number;
    p75_itl_ms: number;
    p75_e2el_ms: number;
    successful_requests: number;
    p95_throughput: number;
    p95_ttft_ms: number;
    p95_tpot_ms: number;
    p95_itl_ms: number;
    p95_e2el_ms: number;
    duration: number;
    total_input_tokens: number;
    p99_throughput: number;
    p99_ttft_ms: number;
    p99_tpot_ms: number;
    p99_itl_ms: number;
    p99_e2el_ms: number;
    id: string;
    total_output_tokens: number;
    min_throughput: number;
    min_ttft_ms: number;
    min_tpot_ms: number;
    min_itl_ms: number;
    min_e2el_ms: number;
    request_throughput: number;
    max_throughput: number;
    max_ttft_ms: number;
    max_tpot_ms: number;
    max_itl_ms: number;
    max_e2el_ms: number;
    simulation_id: string;
    input_throughput: number;
    mean_ttft_ms: number;
    mean_tpot_ms: number;
    mean_itl_ms: number;
    mean_e2el_ms: number;
    created_at: string;
};
export type SimulationAnalysisInput = {
    field1?: string;
    field2?: string;
};
// create zustand store
export const useSimulation = create<{
    totalPages: number;
    totalUsers: number;
    filters: any;
    loading: boolean;
    simulations: Simulation[]
    modelClusterDetails: ModelClusterDetails | null,
    selectedSimulation: Simulation | null,
    simulationResult: SimulationResult | null,
    simulationAnalysisData: any | null,

    getSimulations: (parms: GetsimulationParams) => void;
    fetchSimulations: (params: GetsimulationParams) => Promise<Simulation[]>;
    
}>((set, get) => ({
    filters: {},
    totalPages: 0,
    totalUsers: 0,
    loading: true,
    simulations: [],
    modelClusterDetails: null,
    selectedSimulation: null,
    simulationResult: null,
    simulationAnalysisData: null,

    setSelectedSimulation: (simulation: Simulation) => {
        set({ selectedSimulation: simulation });
    },

    fetchSimulations: async (params: GetsimulationParams) => {
        Object.keys(params)
            .forEach((key) => {
                if (!params[key]) {
                    delete params[key];
                }
            });

        set({ loading: true });
        try {
            const response: any = await AppRequest.Get(`${tempApiBaseUrl}/simulation`, {
                params: {
                    ...params,
                    search: Boolean(params.email),
                }
            });
            set({ totalPages: response.data.total_pages, totalUsers: response.data.total_record });
            const listData = response.data;
            const updatedListData = listData.simulations
            return updatedListData;
        } catch (error) {
            console.error("Error creating model:", error);
        } finally {
            set({ loading: false });
        }
    },

    getSimulations: async (params: GetsimulationParams,) => {
        let updatedListData = await get().fetchSimulations(params);
        console.log('updatedListData', updatedListData)
        if (params.page !== 1) {
            updatedListData = [...get().simulations, ...updatedListData];
        }
        set({ simulations: updatedListData, filters: params });
    },

    

}));