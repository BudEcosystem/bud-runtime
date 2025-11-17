import { useSocket } from "@novu/notification-center";
import { useCallback, useEffect, useState, useRef } from "react";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

export type WorkflowStatus = 'idle' | 'loading' | 'success' | 'failed';

interface WorkflowStep {
  id: string;
  title: string;
  payload: any;
  description: string;
}

interface UsePromptSchemaWorkflowProps {
  workflowId?: string;
  onCompleted?: () => void;
  onFailed?: () => void;
}

/**
 * Hook to handle prompt schema workflow status via socket notifications
 * Based on the pattern from CommonStatus.tsx
 *
 * Workflow structure:
 * - events_field_id: 'prompt_schema_events'
 * - success_payload_type: 'perform_prompt_schema'
 * - Step IDs: validation, code_generation, save_prompt_configuration
 */
export const usePromptSchemaWorkflow = ({
  workflowId,
  onCompleted,
  onFailed,
}: UsePromptSchemaWorkflowProps = {}) => {
  const [status, setStatus] = useState<WorkflowStatus>('idle');
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [loading, setLoading] = useState(false);
  const { socket } = useSocket();
  const timeoutRef = useRef<number | null>(null);

  // Fetch workflow data when workflowId changes
  useEffect(() => {
    if (!workflowId || loading) return;

    const getWorkflow = async () => {
      setSteps([]);
      setLoading(true);

      try {
        console.log(`[usePromptSchemaWorkflow] Fetching workflow: ${workflowId}`);
        const response: any = await AppRequest.Get(`${tempApiBaseUrl}/workflows/${workflowId}`);
        const data = response?.data;

        if (data?.workflow_steps?.prompt_schema_events) {
          const workflowSteps = data.workflow_steps.prompt_schema_events.steps || [];
          console.log(`[usePromptSchemaWorkflow] Loaded ${workflowSteps.length} steps:`, workflowSteps);
          setSteps(workflowSteps);

          // Check if workflow is already completed/failed
          const workflowStatus = data.workflow_steps.prompt_schema_events.status;
          if (workflowStatus === 'COMPLETED') {
            console.log(`[usePromptSchemaWorkflow] Workflow already completed`);
            setStatus('success');
          } else if (workflowStatus === 'FAILED') {
            console.log(`[usePromptSchemaWorkflow] Workflow already failed`);
            setStatus('failed');
          }
        } else {
          console.warn(`[usePromptSchemaWorkflow] No prompt_schema_events found in workflow response`);
        }
      } catch (error) {
        console.error('[usePromptSchemaWorkflow] Error fetching workflow:', error);
      } finally {
        setLoading(false);
      }
    };

    getWorkflow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  const handleNotification = useCallback(async (data: any) => {
    try {
      if (!data || !data.message || !data.message.payload) {
        return;
      }

      const payload = data.message.payload;

      // Only process events if we have a workflowId AND it matches the payload
      // This ensures each handler only processes events for its own workflow
      if (!workflowId || payload.workflow_id !== workflowId) {
        return;
      }

      console.log(`[usePromptSchemaWorkflow] Received notification:`, {
        type: payload.type,
        category: payload.category,
        event: payload.event,
        status: payload.content?.status,
        workflow_id: payload.workflow_id,
      });

      // Handle prompt schema workflow events
      // Type should be 'perform_prompt_schema' based on actual socket events
      if (payload.type === 'perform_prompt_schema' && payload.category === "internal") {
        console.log(`[usePromptSchemaWorkflow] Processing perform_prompt_schema event`);

        // Update steps based on the event
        setSteps(prevSteps => {
          const newSteps = prevSteps.map((step) =>
            payload.event === step.id &&
            (step.payload?.content?.status !== "COMPLETED" && step.payload?.content?.status !== "FAILED")
              ? { ...step, payload: payload }
              : step
          );
          console.log(`[usePromptSchemaWorkflow] Updated steps:`, newSteps.map(s => ({
            id: s.id,
            status: s.payload?.content?.status
          })));
          return newSteps;
        });

        // Update overall status
        const eventStatus = payload.content?.status;

        if (eventStatus === 'RUNNING' || eventStatus === 'IN_PROGRESS') {
          console.log(`[usePromptSchemaWorkflow] Workflow is running`);
          setStatus('loading');
        }

        // Check for completion
        if (payload.event === "results" && eventStatus === "COMPLETED") {
          console.log(`[usePromptSchemaWorkflow] Workflow completed successfully`);
          setStatus('success');
          onCompleted?.();
        }

        // Check for failure
        if (eventStatus === "FAILED") {
          console.log(`[usePromptSchemaWorkflow] Workflow failed`);
          setStatus('failed');
          onFailed?.();
        }
      }
    } catch (error) {
      console.error('[usePromptSchemaWorkflow] Error handling notification:', error);
    }
  }, [workflowId, onCompleted, onFailed]);

  useEffect(() => {
    if (socket) {
      console.log(`[usePromptSchemaWorkflow] Attaching socket listener`);
      socket.on("notification_received", handleNotification);
    }

    return () => {
      if (socket) {
        console.log(`[usePromptSchemaWorkflow] Removing socket listener`);
        socket.off("notification_received");
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [socket, handleNotification]);

  // Method to manually reset status
  const resetStatus = useCallback(() => {
    console.log(`[usePromptSchemaWorkflow] Resetting status to idle`);
    setStatus('idle');
  }, []);

  // Method to manually set loading status (when API call starts)
  const startWorkflow = useCallback(() => {
    console.log(`[usePromptSchemaWorkflow] Starting workflow - setting status to loading`);
    setStatus('loading');
  }, []);

  // Method to manually set success status (for operations without workflow events)
  const setSuccess = useCallback(() => {
    console.log(`[usePromptSchemaWorkflow] Manually setting status to success`);
    setStatus('success');
    // Auto-reset after 3 seconds
    timeoutRef.current = window.setTimeout(() => {
      console.log(`[usePromptSchemaWorkflow] Auto-resetting status to idle`);
      setStatus('idle');
    }, 3000);
  }, []);

  // Method to manually set failed status (for operations without workflow events)
  const setFailed = useCallback(() => {
    console.log(`[usePromptSchemaWorkflow] Manually setting status to failed`);
    setStatus('failed');
    // Auto-reset after 3 seconds
    timeoutRef.current = window.setTimeout(() => {
      console.log(`[usePromptSchemaWorkflow] Auto-resetting status to idle`);
      setStatus('idle');
    }, 3000);
  }, []);

  return {
    status,
    isLoading: status === 'loading',
    isSuccess: status === 'success',
    isFailed: status === 'failed',
    resetStatus,
    startWorkflow,
    setSuccess,
    setFailed,
    steps, // Expose steps for debugging if needed
  };
};
