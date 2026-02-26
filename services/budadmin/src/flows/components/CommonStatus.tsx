import { useSocket } from "@novu/notification-center";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { calculateEta } from "../utils/calculateETA";
import { WorkflowType } from "src/stores/useWorkflow";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import { StatusEvents } from "./StatusIcons";
import { ProgressWithBudList } from "./ProgressWithBud";
import { StatusEstimatedTime } from "./StatusEstimatedTime";

function printStatus(payload: any) {
    if (payload?.content?.status) {
        return `${payload?.content?.status} ${payload?.content?.title}`;
    }
    return `No status ${payload?.content?.title}`;
}

export default function CommonStatus({
    workflowId,
    extraInfo,
    success_payload_type,
    events_field_id,
    onCompleted,
    onFailed,
    title,
    description,
}: {
    title: string,
    description: React.ReactNode,
    extraInfo?: React.ReactNode,
    workflowId: string,
    success_payload_type:
    'register_cluster'
    | 'get_cluster_recommendations'
    | 'deploy_model'
    | 'perform_model_scanning'
    | 'perform_model_security_scan'
    | 'perform_model_extraction'
    | 'endpoint_deletion'
    | 'cluster_deletion'
    | "add_worker"
    | 'add_worker_to_endpoint'
    | 'delete_worker'
    | 'performance_benchmark'
    | 'deploy_quantization'
    | 'add_adapter'
    | 'evaluate_model'
    | 'guardrail_model_onboarding'
    | 'guardrail_simulation'
    | 'guardrail_deployment'
    | 'usecase_deployment',
    events_field_id:
    'bud_simulator_events'
    | 'budserve_cluster_events'
    | 'create_cluster_events'
    | 'delete_cluster_events'
    | 'delete_endpoint_events'
    | 'model_security_scan_events'
    | 'model_extraction_events'
    | 'bud_serve_cluster_events'
    | 'delete_worker_events'
    | 'quantization_simulator_events'
    | 'quantization_deployment_events'
    | 'adapter_deployment_events'
    | 'evaluation_workflow_events'
    | 'evaluation_events'
    | 'guardrail_onboarding_events'
    | 'guardrail_simulation_events'
    | 'guardrail_deployment_events'
    | 'usecase_deployment_events',
    onCompleted: () => void,
    onFailed: () => void,
}) {
    const [loading, setLoading] = useState(false);
    const [steps, setSteps] = useState([]);
    const [eta, setEta] = useState("");
    // Sub-workflow ID extracted from the events data (may differ from parent workflowId)
    const [eventsWorkflowId, setEventsWorkflowId] = useState<string | null>(null);
    const { socket } = useSocket();

    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const failedEvents = useMemo(() => steps?.filter((event) => event?.payload?.content?.status === 'FAILED'), [steps]);

    useEffect(() => {
        if (failedEvents?.length > 0) {
            onFailed();
        }
    }, [failedEvents]);

    // Events that use the main budapp API (relative URL via AppRequest)
    const useMainApi = events_field_id === 'budserve_cluster_events'
        || events_field_id === "bud_simulator_events"
        || events_field_id === 'guardrail_onboarding_events'
        || events_field_id === 'guardrail_simulation_events'
        || events_field_id === 'guardrail_deployment_events';

    const getWorkflow = async () => {
        if (loading) return;
        setSteps([]);
        setLoading(true);
        // bud_simulator_events, budserve_cluster_events
        let url = `${tempApiBaseUrl}/workflows/${workflowId}`;
        if (useMainApi) {
            url = `/workflows/${workflowId}`;
        }
        const response: any = await AppRequest.Get(success_payload_type == 'performance_benchmark' ? `${tempApiBaseUrl}/workflows/${workflowId}` : url);
        let data: WorkflowType;
        if (useMainApi) {
            data = response?.data;
        } else {
            data = response.data;
        }
        if (success_payload_type == 'performance_benchmark') {
            data = response?.data
        }
        const eventsData = data?.workflow_steps[events_field_id];
        const newSteps = eventsData?.steps;
        setSteps(newSteps);
        // Extract sub-workflow ID from the events data (may differ from parent workflowId)
        if (eventsData?.workflow_id) {
            setEventsWorkflowId(eventsData.workflow_id);
        }
        if (eventsData?.eta) {
            calculateEta(eventsData.eta, setEta);
        }
        console.log('response', response)
        setLoading(false);
    }

    useEffect(() => {
        console.log(`workflowId`, workflowId)
        if (workflowId) {
            getWorkflow();
        }
    }, [workflowId]);

    const handleNotification = useCallback(async (data: any) => {
        console.log(`data`, data)
        try {
            if (!data) {
                return;
            }
            if (data?.message && data?.message?.payload) {
                const notifWorkflowId = data.message.payload.workflow_id;
                // If the notification has no workflow_id, let it through (some flows don't include it in real-time)
                // Otherwise, accept notifications matching either the parent workflow ID or the sub-workflow ID
                if (notifWorkflowId && notifWorkflowId !== workflowId && notifWorkflowId !== eventsWorkflowId) {
                    return;
                }
            }
        } catch (error) {
            return
        }
        console.log(`notification data`, data)
        if (data.message.payload.type === success_payload_type && data.message.payload.category === "internal") {
            setSteps(steps => {
                const newSteps = steps.map((step) =>
                    data.message.payload.event === step.id && (step.payload.content?.status !== "COMPLETED" && step.payload.content?.status !== "FAILED") ?
                        { ...step, payload: data.message.payload }
                        : step)
                return newSteps;
            });
            if (data.message.payload.event == "eta" && data.message.payload.content.message) {
                calculateEta(data.message.payload.content.message, setEta);
            }
        }
        if (data.message.payload.event == "results" && data?.message?.payload?.content?.status === "COMPLETED") {
            timeoutRef.current = setTimeout(() => {
                onCompleted();
            }, 3000);
        }
        if (data?.message?.payload?.content?.status === "FAILED") {
            onFailed();
        }
        console.log(`data.message`, data.message)
    }, [workflowId, eventsWorkflowId, success_payload_type, onCompleted, onFailed]);
    useEffect(() => {
        console.log(`steps`, steps)
        console.log(`eta`, eta)
    }, [steps, eta]);
    useEffect(() => {
        if (socket) {
            socket.on("notification_received", handleNotification);
        }

        return () => {
            if (socket) {
                socket.off("notification_received");
            }
        };
    }, [socket, handleNotification]);

    // Clean up timeout on unmount only
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return <BudDrawerLayout>
        <div className="flex flex-col	justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.9rem] border-b border-[#1F1F1F]">
                <Text_14_400_EEEEEE>
                    {title}
                </Text_14_400_EEEEEE>
                <Text_12_400_757575 className="mt-[.6rem] leading-[150%]">
                    {description}
                </Text_12_400_757575>
            </div>
            {extraInfo && <div className="flex justify-start items-center w-full px-[1.35rem] pt-[1.3rem] pb-[1rem] text-[#B3B3B3] text-[.75rem]">
                {extraInfo}
            </div>}
            <ProgressWithBudList events={steps} />
            <StatusEstimatedTime estimatedTime={eta} />
            <StatusEvents events={steps} />
        </div>
    </BudDrawerLayout>


}
