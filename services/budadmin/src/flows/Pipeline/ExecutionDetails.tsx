import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { ExecutionTimeline } from "@/components/pipelineEditor";
import {
  Text_11_400_808080,
  Text_20_400_FFFFFF,
} from "@/components/ui/text";
import { Empty, Tag } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { useBudPipeline } from "src/stores/useBudPipeline";
import { useEffect, useMemo } from "react";
import { differenceInMinutes } from "date-fns";
import { SpecificationTableItem } from "../components/SpecificationTableItem";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";

const PipelineExecutionDetails = () => {
  const { drawerProps } = useDrawer();
  const { getExecution, selectedExecution } = useBudPipeline();

  const executionId = drawerProps?.executionId as string | undefined;
  const workflow = drawerProps?.workflow;

  useEffect(() => {
    if (executionId) {
      getExecution(executionId);
    }
  }, [executionId, getExecution]);

  const formatMinutesAgo = (value?: string) => {
    if (!value) return "—";
    const minutes = Math.max(0, differenceInMinutes(new Date(), new Date(value)));
    return minutes === 1 ? "1 min ago" : `${minutes} min ago`;
  };

  const startedLabel = useMemo(
    () => formatMinutesAgo(selectedExecution?.started_at),
    [selectedExecution?.started_at]
  );

  const completedLabel = useMemo(
    () => formatMinutesAgo(selectedExecution?.completed_at),
    [selectedExecution?.completed_at]
  );

  const durationLabel = useMemo(() => {
    if (!selectedExecution?.started_at || !selectedExecution?.completed_at) {
      return "—";
    }
    const start = new Date(selectedExecution.started_at).getTime();
    const end = new Date(selectedExecution.completed_at).getTime();
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return "—";
    }
    const totalSeconds = Math.max(0, Math.round((end - start) / 1000));
    if (totalSeconds < 60) {
      return totalSeconds === 1 ? "1 sec" : `${totalSeconds} sec`;
    }
    const totalMinutes = Math.round(totalSeconds / 60);
    return totalMinutes === 1 ? "1 min" : `${totalMinutes} min`;
  }, [selectedExecution?.started_at, selectedExecution?.completed_at]);

  const executionSpecs = useMemo(
    () => [
      { name: "Started", value: startedLabel },
      { name: "Completed", value: completedLabel },
      { name: "Duration", value: durationLabel },
    ],
    [startedLabel, completedLabel, durationLabel]
  );

  return (
    <BudForm data={{}}>
      <BudWraperBox classNames="pt-[0]">
        {selectedExecution ? (
          <>
            <div className="h-[1.25rem]" />
            <BudDrawerLayout>
              <DrawerCard>
                <div className="flex items-start justify-between gap-3 pt-[.4rem]">
                  <div className="flex flex-col gap-3">
                    <Text_20_400_FFFFFF>
                      {workflow?.name || selectedExecution.workflow_name || "Pipeline"}
                    </Text_20_400_FFFFFF>
                    <Text_11_400_808080>{selectedExecution.execution_id}</Text_11_400_808080>
                  </div>
                  <Tag
                    className={`border-0 text-[10px] ${
                      selectedExecution.status === "completed"
                        ? "bg-green-500/20 text-green-500"
                        : selectedExecution.status === "failed"
                        ? "bg-red-500/20 text-red-500"
                        : selectedExecution.status === "running"
                        ? "bg-blue-500/20 text-blue-500"
                        : "bg-gray-500/20 text-gray-500"
                    }`}
                  >
                    {selectedExecution.status}
                  </Tag>
                </div>
                <div className="mt-[1.1rem] flex flex-row flex-wrap gap-y-[1.15rem] mb-[1.1rem]">
                  {executionSpecs.map((item, index) => (
                    <SpecificationTableItem key={index} item={{ ...item, full: false }} valueWidth={80} />
                  ))}
                </div>
              </DrawerCard>
            </BudDrawerLayout>
            <BudDrawerLayout>
              <DrawerTitleCard
                title={"Execution Steps"}
                description="Follow the pipeline path, status, and timing for every step."
              />
              <DrawerCard>
                <div className="mt-3">
                  <ExecutionTimeline execution={selectedExecution} />
                </div>
              </DrawerCard>
            </BudDrawerLayout>
            <BudDrawerLayout>
              <DrawerTitleCard
                title={"Input Parameters"}
                description="Review the inputs provided when this execution was triggered."
              />
              <DrawerCard>
                <pre className="text-[11px] text-gray-400 bg-[#0D0D0D] p-3 rounded border border-[#1F1F1F] overflow-auto max-h-60">
                  {JSON.stringify(selectedExecution.params || {}, null, 2)}
                </pre>
              </DrawerCard>
            </BudDrawerLayout>
          </>
        ) : (
          <div className="form-layout flex items-center justify-center min-h-[300px]">
            <Empty description="Select an execution to view details" />
          </div>
        )}
      </BudWraperBox>
    </BudForm>
  );
};

export default PipelineExecutionDetails;
