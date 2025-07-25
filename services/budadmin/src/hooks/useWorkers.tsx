import { tempApiBaseUrl } from "@/components/environment";
import { Worker } from "cluster";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

export interface IWorker {
    cluster_id: string;
    namespace: string;
    name: string;
    status: string;
    node_name: string;
    utilization: string;
    hardware: string;
    uptime: string;
    last_restart_datetime: string;
    last_updated_datetime: string;
    created_datetime: string;
    node_ip: string;
    cores: number;
    memory: string;
    deployment_status: string;
    id: string;
}


// create zustand store
export const useWorkers = create<{
    workers: IWorker[];
    loading: boolean;
    selectedWorker: IWorker | null;
    getWorkers: (endpointId: string, params?: any, projectId?: string) => Promise<IWorker[]>;
    getWorker: (endpointId: string, workerId: string, reload?: boolean, projectId?: string) => Promise<IWorker>;
    deleteWorker: (endpointId: string, worker: IWorker, projectId?: string) => Promise<any>;
    getWorkerMetrics: (endpointId: string, workerId: string, projectId?: string) => Promise<any>;
    getWorkerLogs: (endpointId: string, workerId: string, projectId?: string) => Promise<any>;
    isMetricsLoading: boolean;
    isLogsLoading: boolean;
}>((set, get) => ({

    getWorkerLogs: async (endpointId: string, workerId: string, projectId?) => {
        set({ isLogsLoading: true });
        try {
            const response: any = await AppRequest.Get(
                `${tempApiBaseUrl}/endpoints/${endpointId}/workers/${workerId}/logs`,
                {
                    headers: {
                        "x-resource-type": "project",
                        "x-entity-id": projectId,
                    },
                }
            );
            return response?.data?.logs;
        } catch (error) {
            console.error("Error fetching logs:", error);
        } finally {
            set({ isLogsLoading: false });
        }
    },

    getWorkerMetrics: async (endpointId: string, workerId: string, projectId?) => {
        set({ isMetricsLoading: true });
        try {
            const response: any = await AppRequest.Get(
                `${tempApiBaseUrl}/endpoints/${endpointId}/workers/${workerId}/metrics`,
                {
                    headers: {
                        "x-resource-type": "project",
                        "x-entity-id": projectId,
                    },
                }
            );
            return response?.data?.metrics;
        } catch (error) {
            console.error("Error fetching metrics:", error);
        } finally {
            set({ isMetricsLoading: false });
        }
    },


    getWorker: async (endpointId: string, workerId: string, reload = false, projectId?) => {
        set({ loading: true });
        try {
            const response: any = await AppRequest.Get(
                `${tempApiBaseUrl}/endpoints/${endpointId}/workers/${workerId}`,
                {
                    params: {
                        reload,
                    },
                    headers: {
                        "x-resource-type": "project",
                        "x-entity-id": projectId,
                    },
                }
            );
            set({ selectedWorker: response.data?.worker, loading: false });
            return response?.data?.worker;
        } catch (error) {
            console.error("Error fetching worker:", error);
            set({ loading: false });
        }
    },

    getWorkers: async (endpointId: string, params?: any, projectId?) => {
        set({ loading: true });
        try {
            const response: any = await AppRequest.Get(
                `${tempApiBaseUrl}/endpoints/${endpointId}/workers`,
                {
                    params: {
                        ...params,
                    },
                    headers: {
                        "x-resource-type": "project",
                        "x-entity-id": projectId,
                    },
                }
            );
            set({ workers: response.data?.workers, loading: false });
            return response?.data?.workers;
        } catch (error) {
            console.error("Error fetching workers:", error);
            set({ loading: false });
        }
    },

    workers: [],
    loading: false,
    isMetricsLoading: true,
    isLogsLoading: true,
    selectedWorker: null,

    deleteWorker: async (endpointId: string, _worker: IWorker, projectId?) => {
        const response: any = await AppRequest.Post(
            `${tempApiBaseUrl}/endpoints/delete-worker`,
            {
                endpoint_id: endpointId,
                worker_id: _worker.id,
                worker_name: _worker.name,
            },
            {
                headers: {
                    "x-resource-type": "project",
                    "x-entity-id": projectId,
                },
            }
        );

        get().getWorkers(endpointId);
        return response;
    },

}));