import { useSocket } from "@novu/notification-center";
import React, { useCallback, useEffect, useMemo, useState } from "react";
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
    | 'evaluate_model',
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
    | 'evaluation_events',
    onCompleted: () => void,
    onFailed: () => void,
}) {
    const [loading, setLoading] = useState(false);
    const [steps, setSteps] = useState([]);
    const [eta, setEta] = useState("");
    const { socket } = useSocket();

    let timeout: any;
    const failedEvents = useMemo(() => steps?.filter((event) => event?.payload?.content?.status === 'FAILED'), [steps]);

    useEffect(() => {
        if (failedEvents?.length > 0) {
            onFailed();
        }
    }, [failedEvents]);

    const getWorkflow = async () => {
        if (loading) return;
        setSteps([]);
        setLoading(true);
        // bud_simulator_events, budserve_cluster_events
        let url = `${tempApiBaseUrl}/workflows/${workflowId}`;
        if (events_field_id === 'budserve_cluster_events' || events_field_id === "bud_simulator_events") {
            url = `/workflows/${workflowId}`;
        }
        const response: any = await AppRequest.Get(success_payload_type == 'performance_benchmark' ? `${tempApiBaseUrl}/workflows/${workflowId}` : url);
        let data: WorkflowType;
        if (events_field_id === 'budserve_cluster_events' || events_field_id === "bud_simulator_events") {
            data = response?.data;
        } else {
            data = response.data;
        }
        if (success_payload_type == 'performance_benchmark') {
            data = response?.data
        }
        const newSteps = data?.workflow_steps[events_field_id]?.steps;
        setSteps(newSteps);
        if (data?.workflow_steps[events_field_id]?.eta) {
            calculateEta(data?.workflow_steps[events_field_id]?.eta, setEta);
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
            if (data?.message && data?.message?.payload && data?.message?.payload?.workflow_id !== workflowId) {
                return;
            }
        } catch (error) {
            return
        }
        console.log(`notification data`, data)
        if (data.message.payload.type === success_payload_type && data.message.payload.category === "internal") {
            setSteps(steps => {
                const newSteps = steps.map((step) =>
                    data.message.payload.event === step.id && (step.payload.content?.status !== "COMPLETED" && step.payload.content?.status !== "FAILED") ?
                        // data.message.payload.event && step.payload?.content?.title === data.message.payload.content.title ?
                        { ...step, payload: data.message.payload }
                        : step)
                // console.log(`newSteps`, newSteps, data.message?.payload, printStatus(data.message.payload), newSteps?.map(step => printStatus(step.payload)))
                return newSteps;
            });
            if (data.message.payload.event == "eta" && data.message.payload.content.message) {
                // map the eta to the workflow
                // console.log(`print eta`, data.message.payload.content.message)
                calculateEta(data.message.payload.content.message, setEta);
            }
        }
        if (data.message.payload.event == "results" && data?.message?.payload?.content?.status === "COMPLETED") {
            timeout = setTimeout(() => {
                onCompleted();
            }, 3000);
        }
        if (data?.message?.payload?.content?.status === "FAILED") {
            // getWorkflow();
            onFailed();
        }
        console.log(`data.message`, data.message)
    }, [steps, workflowId]);

    useEffect(() => {
        if (socket) {
            socket.on("notification_received", handleNotification);
        }

        return () => {
            if (socket) {
                socket.off("notification_received");
            }
            if (timeout) {
                clearTimeout(timeout);
            }
        };
    }, [socket]);

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
