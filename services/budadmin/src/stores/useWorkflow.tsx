import { tempApiBaseUrl } from "@/components/environment";
import { errorToast, successToast } from "@/components/toast";
import { TagListeItem } from "src/flows/components/TagsList";
import { Provider } from "src/hooks/useCloudProviders";
import { Cluster } from "src/hooks/useCluster";
import { Model, ScanResult } from "src/hooks/useModels";
import { Project } from "src/hooks/useProjects";
import { IDeploymentTemplate } from "src/hooks/useTemplates";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { Credentials } from "./useProprietaryCredentials";
import { Endpoint } from "src/hooks/useEndPoint";
import { QuantizeConfig } from "./useDeployModel";

type BudSimulatorPayload = {
    category?: string;
    type?: string;
    event?: string;
    workflow_id?: string;
    source?: string;
    content?: {
        title: string;
        message: string;
        status: string;
        primary_action: string;
        secondary_action: string;
        progress?: number;
        result?: string;
    };
}

type BudSimulatorSteps = {
    payload?: BudSimulatorPayload;
    title: string;
    description: string;
    id: string;
}

export type BudSimilatorEvent = {
    steps: BudSimulatorSteps[];
    eta: number;
    object: string;
    status: string;
    workflow_id: string;
    workflow_name: string;
    progress_type: string;
    recommended_cluster_count?: number;
    metadata?: {
        tool_calling_parser_type?: string;
        reasoning_parser_type?: string;
        chat_template?: string;
        [key: string]: any;
    };
}



export type WorkflowListItem = {
    id: string;
    title: string;
    icon: string;
    progress: BudSimilatorEvent;
    workflow_type: string;
    total_steps: number;
    status: string;
    current_step: number;
    reason: string;
    modified_at?: string;
    created_at?: string;
    tag?: string;
}

type DeployEndpointDetails = {
    result: {
        model: string;
        concurrency: number;
        target_ttft: number;
        input_tokens: number;
        output_tokens: number;
        deployment_url: string;
        target_e2e_latency: number;
        target_throughput_per_user: number;
    }
    namespace: string;
    cluster_id: string;
    workflow_id: string
    simulator_id: string
    credentials_id: string;
    benchmark_status: boolean;
    performance_status: boolean;
}

type QuantizationDetails = {
    quantized_model_name: string;
    target_device: string;
    method: string;
    target_type: string;
    activation_config: QuantizeConfig;
    weight_config: QuantizeConfig;
    cluster_id: string;
    simulation_id: string;
    quantized_model_id: string;
    quantized_model: Model;
    quantization_data: any;
}

type AdapterDetails = {
    adapter_name: string;
    adapter_model_id: string;
    endpoint_id: string;
    adapter_id: string;
}


export type WorkflowType = {
    current_step: number;
    workflow_id: string;
    reason: string;
    status: string;
    total_steps: number;
    object: string;
    message: string;
    experiment_id?: string;
    created_at?: string;
    updated_at?: string;
    workflow_steps: {
        model: Model;
        add_model_modality: string[];
        cluster?: Cluster;
        project?: Project
        template?: IDeploymentTemplate;
        bud_simulator_events?: BudSimilatorEvent;
        budserve_cluster_events?: BudSimilatorEvent;
        create_cluster_events?: BudSimilatorEvent;
        delete_cluster_events?: BudSimilatorEvent;
        delete_endpoint_events?: BudSimilatorEvent;
        model_security_scan_events?: BudSimilatorEvent;
        model_extraction_events?: BudSimilatorEvent;
        evaluation_events?: BudSimilatorEvent;
        endpoint_name?: string;
        deploy_config?: any;
        icon?: string;
        uri?: string;
        simulator_id?: string;
        provider_type?: string;
        provider: Provider;
        cloud_model?: Model;
        cloud_model_id?: string;
        provider_id?: string;
        model_id?: string;
        workflow_execution_status?: string;
        leaderboard?: any;
        name: string;
        ingress_url: string;
        tags: TagListeItem[];
        author: string;
        description: string;
        security_scan_result_id: string;
        security_scan_result: ScanResult | null;
        credential?: Credentials;
        endpoint_details?: DeployEndpointDetails;
        endpoint?: Endpoint;
        quantization_config?: QuantizationDetails;
        adapter_config?: AdapterDetails;
        stage_data?: {
            trait_ids?: any;
        };
        trait_ids?: string;
        dataset_ids?: string[];
        traits_details?: any;
        experiment_id?: string;
        bud_prompt_id?: string;
        benchmark_id?: string;
    }
        template_id?: string;
}

export const useWorkflow = create<{
    workflowList: WorkflowListItem[];
    getWorkflowList: () => void;
}>((set, get) => ({
    workflowList: [],
    getWorkflowList: async () => {
        try {
            const response: any = await AppRequest.Get(`${tempApiBaseUrl}/workflows`, {
                params: {
                    order_by: "-modified_at"
                }
            });
            if (response) {
                const workflows: WorkflowListItem[] = response.data.workflows;
                set({
                    workflowList: workflows
                });
                return workflows;
            }
            return false;
            // successToast(response.data.message);
        } catch (error) {
            return false;
        }
    },
}));
