"use client";
import React from "react";
import { Flex, Box } from "@radix-ui/themes";
import { PipelineExecution, PipelineStepExecution } from "src/stores/useBudPipeline";
import { Tag, Tooltip, Collapse, Empty } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined,
  RightOutlined,
  DownOutlined,
} from "@ant-design/icons";
import { formatDistanceToNow, differenceInSeconds } from "date-fns";

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bgColor: string }> = {
  pending: {
    icon: <ClockCircleOutlined />,
    color: "#8c8c8c",
    bgColor: "#8c8c8c20",
  },
  running: {
    icon: <LoadingOutlined spin />,
    color: "#1890ff",
    bgColor: "#1890ff20",
  },
  completed: {
    icon: <CheckCircleOutlined />,
    color: "#52c41a",
    bgColor: "#52c41a20",
  },
  skipped: {
    icon: <MinusCircleOutlined />,
    color: "#8c8c8c",
    bgColor: "#8c8c8c10",
  },
  failed: {
    icon: <CloseCircleOutlined />,
    color: "#f5222d",
    bgColor: "#f5222d20",
  },
};

interface StepTimelineItemProps {
  step: PipelineStepExecution;
  isLast: boolean;
  onSelect?: (step: PipelineStepExecution) => void;
  isSelected?: boolean;
}

const StepTimelineItem: React.FC<StepTimelineItemProps> = ({
  step,
  isLast,
  onSelect,
  isSelected,
}) => {
  const config = statusConfig[step.status];
  const duration =
    step.started_at && step.completed_at
      ? differenceInSeconds(new Date(step.completed_at), new Date(step.started_at))
      : null;

  const [isExpanded, setIsExpanded] = React.useState(false);
  const hasOutputs = Object.keys(step.outputs || {}).length > 0;

  return (
    <Flex className="relative">
      {/* Timeline line */}
      {!isLast && (
        <div
          className="absolute left-[15px] top-[32px] w-0.5 h-[calc(100%-16px)]"
          style={{ backgroundColor: config.color + "40" }}
        />
      )}

      {/* Status icon */}
      <Flex
        align="center"
        justify="center"
        className="w-8 h-8 rounded-full flex-shrink-0 z-10"
        style={{ backgroundColor: config.bgColor, color: config.color }}
      >
        {config.icon}
      </Flex>

      {/* Content */}
      <Box
        className={`
          ml-3 flex-1 mb-4 p-3 rounded-lg border cursor-pointer transition-all
          ${isSelected ? "border-blue-500 bg-[#1a2744]" : "border-[#2F3035] bg-[#1A1A1A]"}
          hover:border-blue-400
        `}
        onClick={() => onSelect?.(step)}
      >
        <Flex justify="between" align="center">
          <Flex align="center" gap="2">
            <span className="text-white text-sm font-medium">{step.name}</span>
            <Tag
              className="border-0 text-[10px]"
              style={{ backgroundColor: config.bgColor, color: config.color }}
            >
              {step.status}
            </Tag>
          </Flex>
          <Flex align="center" gap="2">
            {/* {duration !== null && (
              <span className="text-gray-500 text-xs">{duration}s</span>
            )} */}
            {step.started_at && (
              <Tooltip title={new Date(step.started_at).toLocaleString()}>
                <span className="text-gray-600 text-[10px]">
                  {formatDistanceToNow(new Date(step.started_at), { addSuffix: true })}
                </span>
              </Tooltip>
            )}
          </Flex>
        </Flex>

        {/* Error message */}
        {step.error && (
          <Box className="mt-2 p-2 rounded bg-red-500/10 border border-red-500/20">
            <span className="text-red-400 text-xs">{step.error}</span>
          </Box>
        )}

        {/* Outputs */}
        {hasOutputs && (
          <Box className="mt-2">
            <Flex
              align="center"
              gap="1"
              className="text-gray-500 text-xs cursor-pointer hover:text-gray-300"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
            >
              {isExpanded ? <DownOutlined /> : <RightOutlined />}
              <span>Outputs ({Object.keys(step.outputs).length})</span>
            </Flex>
            {isExpanded && (
              <Box className="mt-2 p-2 rounded bg-[#0D0D0D] overflow-auto max-h-40">
                <pre className="text-[10px] text-gray-400 whitespace-pre-wrap">
                  {JSON.stringify(step.outputs, null, 2)}
                </pre>
              </Box>
            )}
          </Box>
        )}
      </Box>
    </Flex>
  );
};

interface ExecutionTimelineProps {
  execution: PipelineExecution;
  onStepSelect?: (step: PipelineStepExecution) => void;
  selectedStepId?: string;
}

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({
  execution,
  onStepSelect,
  selectedStepId,
}) => {
  const overallConfig = statusConfig[execution.status];
  const duration =
    execution.started_at && execution.completed_at
      ? differenceInSeconds(
          new Date(execution.completed_at),
          new Date(execution.started_at)
        )
      : null;

  return (
    <div>
      {/* Steps timeline */}
      {/* <Box className="mt-4"> */}
        {/* <div className="text-gray-500 text-xs mb-3">Execution Steps</div> */}
        {execution.steps.length > 0 ? (
          execution.steps.map((step, index) => (
            <StepTimelineItem
              key={step.step_id}
              step={step}
              isLast={index === execution.steps.length - 1}
              onSelect={onStepSelect}
              isSelected={selectedStepId === step.step_id}
            />
          ))
        ) : (
          <Empty
            description="No steps executed yet"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            className="py-8"
          />
        )}
      {/* </Box> */}

      {/* Outputs */}
      {Object.keys(execution.outputs).length > 0 && (
        <Box className="mt-4 p-3 rounded bg-green-500/5 border border-green-500/20">
          <div className="text-green-500 text-xs mb-2">Workflow Outputs</div>
          <pre className="text-[11px] text-gray-400 whitespace-pre-wrap overflow-auto max-h-40">
            {JSON.stringify(execution.outputs, null, 2)}
          </pre>
        </Box>
      )}

      {/* Error */}
      {execution.error && (
        <Box className="mt-4 p-3 rounded bg-red-500/10 border border-red-500/20">
          <div className="text-red-500 text-xs mb-1">Execution Error</div>
          <span className="text-red-400 text-sm">{execution.error}</span>
        </Box>
      )}
    </div>
  );
};

export default ExecutionTimeline;
