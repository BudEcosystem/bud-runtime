import { Message } from "ai";
import { Endpoint } from "./deployment";



export type Session = {
    id: string;
    name: string;
    total_tokens: number;
    created_at: string;
    modified_at: string;
    chat_setting_id?: string;
    active?: boolean;
    selectedDeployment?: Endpoint;
    deploymentLocked?: boolean;
};

export type Usage = {
    completionTokens: number;
    promptTokens: number;
    totalTokens: number;
};

export type Metrics = {
    e2e_latency: number;
    throughput: number;
    ttft: number;
    itl: number;
}

export type Settings = {
    id: string;
    name: string;
    system_prompt: string;
    temperature: number;
    limit_response_length: boolean;
    sequence_length: number;
    context_overflow_policy: string;
    stop_strings: string[];
    top_k_sampling: number;
    repeat_penalty: number;
    top_p_sampling: number;
    min_p_sampling: number;
    enable_structured_json_schema: boolean;
    structured_json_schema: string;
    is_valid_json_schema: boolean;
    created_at: string;
    modified_at: string;
}

export type Note = {
    id: string;
    note: string;
    created_at: string;
    modified_at: string;
    chat_session_id: string;
}

export type SavedMessage = Message & {
    feedback: string;
}
