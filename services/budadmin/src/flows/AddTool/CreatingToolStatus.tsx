import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { ProgressWithBudList } from "src/flows/components/ProgressWithBud";
import { StatusEstimatedTime } from "src/flows/components/StatusEstimatedTime";
import { StatusEvents } from "src/flows/components/StatusIcons";
import { BudSimulatorSteps } from "src/stores/useDeployModel";
import { useAddTool, ToolCreationEvent } from "@/stores/useAddTool";
import { useSocket } from "@novu/notification-center";
import { AppRequest } from "src/pages/api/requests";
import { calculateEta } from "src/flows/utils/calculateETA";

// Helper to create a step with all required fields
const createStep = (
  id: string,
  title: string,
  description: string,
  status: string
): BudSimulatorSteps => ({
  id,
  title,
  description,
  payload: {
    category: "internal",
    type: "create_tool",
    event: id,
    workflow_id: "",
    source: "budadmin",
    content: {
      title,
      message: description,
      status,
      primary_action: "",
      secondary_action: "",
      progress: 0,
    },
  },
});

// Initial steps for tool creation progress
const initialToolCreationSteps: BudSimulatorSteps[] = [
  createStep(
    "parse-spec",
    "Parsing Specification",
    "Reading and parsing the OpenAPI/API documentation",
    "IN_PROGRESS"
  ),
  createStep(
    "identify-endpoints",
    "Identifying Endpoints",
    "Extracting endpoint definitions",
    "PENDING"
  ),
  createStep(
    "generate-tools",
    "Generating Tools",
    "Creating MCP-compatible tool definitions",
    "PENDING"
  ),
  createStep(
    "results",
    "Finalizing",
    "Completing tool creation",
    "PENDING"
  ),
];

export default function CreatingToolStatus() {
  const { openDrawerWithStep } = useDrawer();
  const { workflowId, isCreating, fetchWorkflow, addCreationEvent, creationEvents } = useAddTool();
  const [steps, setSteps] = useState(initialToolCreationSteps);
  const [eta, setEta] = useState("Calculating...");
  const [isCompleted, setIsCompleted] = useState(false);
  const [hasFailed, setHasFailed] = useState(false);
  const { socket } = useSocket();

  let timeout: NodeJS.Timeout | undefined;

  // Check for failed events
  const failedEvents = useMemo(
    () => steps?.filter((event) => event?.payload?.content?.status === "FAILED"),
    [steps]
  );

  useEffect(() => {
    if (failedEvents?.length > 0) {
      setHasFailed(true);
    }
  }, [failedEvents]);

  // Fetch initial workflow state
  const getWorkflowStatus = useCallback(async () => {
    if (!workflowId) return;

    try {
      const response = await AppRequest.Get(`/tools/workflow/${workflowId}`);
      const data = response?.data;

      if (data?.step_data?.tool_creation_events?.steps) {
        setSteps(data.step_data.tool_creation_events.steps);
      }
      if (data?.step_data?.tool_creation_events?.eta) {
        calculateEta(data.step_data.tool_creation_events.eta, setEta);
      }
    } catch (error) {
      console.error("Failed to fetch workflow status:", error);
    }
  }, [workflowId]);

  useEffect(() => {
    if (workflowId) {
      getWorkflowStatus();
    }
  }, [workflowId, getWorkflowStatus]);

  // Handle socket notifications
  const handleNotification = useCallback(
    async (data: any) => {
      try {
        if (!data?.message?.payload) return;

        const payload = data.message.payload;

        // Check if this notification is for our workflow
        if (payload.workflow_id !== workflowId) return;

        // Check if this is a tool creation event
        if (payload.type !== "create_tool" || payload.category !== "internal") return;

        // Update steps based on the event
        setSteps((prevSteps) => {
          return prevSteps.map((step) =>
            payload.event === step.id &&
            step.payload.content?.status !== "COMPLETED" &&
            step.payload.content?.status !== "FAILED"
              ? { ...step, payload }
              : step
          );
        });

        // Handle ETA updates
        if (payload.event === "eta" && payload.content?.message) {
          calculateEta(payload.content.message, setEta);
        }

        // Handle completion
        if (payload.event === "results" && payload.content?.status === "COMPLETED") {
          timeout = setTimeout(() => {
            setIsCompleted(true);
          }, 1500);
        }

        // Handle failure
        if (payload.content?.status === "FAILED") {
          setHasFailed(true);
        }

        // Track event in store
        addCreationEvent({
          title: payload.content?.title || payload.event,
          message: payload.content?.message || "",
          status: payload.content?.status === "COMPLETED" ? "completed" :
                 payload.content?.status === "FAILED" ? "failed" :
                 payload.content?.status === "IN_PROGRESS" ? "in_progress" : "pending",
        });
      } catch (error) {
        console.error("Error handling notification:", error);
      }
    },
    [workflowId, addCreationEvent]
  );

  // Setup socket listener
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
  }, [socket, handleNotification]);

  const handleNext = () => {
    openDrawerWithStep("tool-creation-success");
  };

  const handleBack = () => {
    openDrawerWithStep("openapi-specification");
  };

  return (
    <BudForm
      data={{}}
      nextText={isCompleted ? "View Tools" : "Creating..."}
      onNext={handleNext}
      onBack={hasFailed ? handleBack : undefined}
      backText={hasFailed ? "Try Again" : undefined}
      disableNext={!isCompleted}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.9rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>
                {hasFailed ? "Tool Creation Failed" : isCompleted ? "Tool Created Successfully" : "Creating Tool"}
              </Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.6rem] leading-[150%]">
                {hasFailed
                  ? "There was an error creating your tools. Please try again."
                  : isCompleted
                  ? "Your tools have been created and are ready to use."
                  : "Your tool is being created, it may take a few moments to finish"}
              </Text_12_400_757575>
            </div>
            <ProgressWithBudList events={steps} />
            {!isCompleted && !hasFailed && <StatusEstimatedTime estimatedTime={eta} />}
            <StatusEvents events={steps} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
