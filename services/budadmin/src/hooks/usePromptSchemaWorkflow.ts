import { useSocket } from "@novu/notification-center";
import { useCallback, useEffect, useState } from "react";

export type WorkflowStatus = 'idle' | 'loading' | 'success' | 'failed';

interface UsePromptSchemaWorkflowProps {
  workflowId?: string;
  onCompleted?: () => void;
  onFailed?: () => void;
}

/**
 * Hook to handle prompt schema workflow status via socket notifications
 * Based on the pattern from CommonStatus.tsx
 */
export const usePromptSchemaWorkflow = ({
  workflowId,
  onCompleted,
  onFailed,
}: UsePromptSchemaWorkflowProps = {}) => {
  const [status, setStatus] = useState<WorkflowStatus>('idle');
  const { socket } = useSocket();

  const handleNotification = useCallback(async (data: any) => {
    try {
      if (!data || !data.message || !data.message.payload) {
        return;
      }

      // Filter by workflow_id if provided
      if (workflowId && data.message.payload.workflow_id !== workflowId) {
        return;
      }

      // Handle prompt schema workflow events
      // Adjust the type based on actual backend event type
      if (data.message.payload.type === 'prompt_schema_workflow' && data.message.payload.category === "internal") {
        const eventStatus = data.message.payload.content?.status;

        if (eventStatus === 'RUNNING' || eventStatus === 'IN_PROGRESS') {
          setStatus('loading');
        } else if (eventStatus === 'COMPLETED' || data.message.payload.event === 'results') {
          setStatus('success');
          if (onCompleted) {
            // Add a small delay before callback
            setTimeout(() => {
              onCompleted();
            }, 1000);
          }
        } else if (eventStatus === 'FAILED') {
          setStatus('failed');
          if (onFailed) {
            onFailed();
          }
        }
      }
    } catch (error) {
      console.error('Error handling prompt schema workflow notification:', error);
    }
  }, [workflowId, onCompleted, onFailed]);

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

  // Method to manually reset status
  const resetStatus = useCallback(() => {
    setStatus('idle');
  }, []);

  // Method to manually set loading status (when API call starts)
  const startWorkflow = useCallback(() => {
    setStatus('loading');
  }, []);

  return {
    status,
    isLoading: status === 'loading',
    isSuccess: status === 'success',
    isFailed: status === 'failed',
    resetStatus,
    startWorkflow,
  };
};
