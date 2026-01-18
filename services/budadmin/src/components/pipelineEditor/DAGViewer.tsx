"use client";
import React from "react";
import { Flex, Box } from "@radix-ui/themes";
import { DAGDefinition, PipelineStep, PipelineStepExecution } from "src/stores/useBudPipeline";
import { Tooltip, Tag } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined,
} from "@ant-design/icons";

// Action type icons and colors
const actionConfig: Record<string, { icon: string; color: string }> = {
  http_request: { icon: "🌐", color: "#1890ff" },
  transform: { icon: "🔄", color: "#722ed1" },
  log: { icon: "📝", color: "#52c41a" },
  delay: { icon: "⏱️", color: "#faad14" },
  aggregate: { icon: "📊", color: "#eb2f96" },
  set_output: { icon: "📤", color: "#13c2c2" },
  conditional: { icon: "🔀", color: "#fa8c16" },
  fail: { icon: "❌", color: "#f5222d" },
};

// Status icons
const statusIcons: Record<string, React.ReactNode> = {
  pending: <ClockCircleOutlined className="text-gray-500" />,
  running: <LoadingOutlined className="text-blue-500" spin />,
  completed: <CheckCircleOutlined className="text-green-500" />,
  skipped: <MinusCircleOutlined className="text-gray-400" />,
  failed: <CloseCircleOutlined className="text-red-500" />,
};

interface StepNodeProps {
  step: PipelineStep;
  execution?: PipelineStepExecution;
  isFirst?: boolean;
  isLast?: boolean;
  parallelWith?: string[];
  onSelect?: (step: PipelineStep) => void;
  isSelected?: boolean;
}

const StepNode: React.FC<StepNodeProps> = ({
  step,
  execution,
  isFirst,
  isLast,
  parallelWith,
  onSelect,
  isSelected,
}) => {
  const config = actionConfig[step.action] || { icon: "⚙️", color: "#8c8c8c" };
  const status = (execution?.status?.toLowerCase()) || "pending";

  return (
    <Tooltip
      title={
        <div className="text-xs">
          <div className="font-semibold mb-1">{step.name}</div>
          <div>Action: {step.action}</div>
          {step.condition && <div>Condition: {step.condition}</div>}
          {execution?.started_at && (
            <div>Started: {new Date(execution.started_at).toLocaleTimeString()}</div>
          )}
          {execution?.completed_at && (
            <div>Completed: {new Date(execution.completed_at).toLocaleTimeString()}</div>
          )}
          {execution?.error && <div className="text-red-400">Error: {execution.error}</div>}
        </div>
      }
    >
      <Flex
        direction="column"
        align="center"
        className={`
          relative p-3 rounded-lg border-2 cursor-pointer transition-all min-w-[140px]
          ${isSelected ? "border-blue-500 bg-[#1a2744]" : "border-[#2F3035] bg-[#1A1A1A]"}
          hover:border-blue-400 hover:shadow-lg
        `}
        onClick={() => onSelect?.(step)}
        style={{ borderLeftColor: config.color, borderLeftWidth: 4 }}
      >
        {/* Status indicator */}
        <div className="absolute -top-2 -right-2 bg-[#0a0a0a] rounded-full p-1">
          {statusIcons[status]}
        </div>

        {/* Icon */}
        <div className="text-2xl mb-1">{config.icon}</div>

        {/* Name */}
        <div className="text-white text-xs font-medium text-center truncate max-w-[120px]">
          {step.name}
        </div>

        {/* Action type */}
        <Tag
          className="mt-1 text-[10px] border-0"
          style={{ backgroundColor: `${config.color}20`, color: config.color }}
        >
          {step.action}
        </Tag>

        {/* Condition indicator */}
        {step.condition && (
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2">
            <Tooltip title={`Condition: ${step.condition}`}>
              <span className="text-[10px] bg-yellow-500/20 text-yellow-500 px-1 rounded">
                if
              </span>
            </Tooltip>
          </div>
        )}

        {/* Parallel indicator */}
        {parallelWith && parallelWith.length > 0 && (
          <div className="absolute -top-2 left-2 text-[9px] bg-purple-500/20 text-purple-400 px-1 rounded">
            ∥ parallel
          </div>
        )}
      </Flex>
    </Tooltip>
  );
};

interface ConnectionLineProps {
  hasCondition?: boolean;
  isParallel?: boolean;
}

const ConnectionLine: React.FC<ConnectionLineProps> = ({ hasCondition, isParallel }) => (
  <Flex direction="column" align="center" className="h-8 relative">
    <div
      className={`w-0.5 h-full ${
        isParallel ? "bg-purple-500/50" : "bg-[#3F3F3F]"
      }`}
    />
    <div
      className={`absolute bottom-0 w-2 h-2 border-l-2 border-b-2 rotate-[-45deg] ${
        isParallel ? "border-purple-500/50" : "border-[#3F3F3F]"
      }`}
    />
    {hasCondition && (
      <div className="absolute top-1/2 -translate-y-1/2 -right-6 text-[9px] bg-yellow-500/20 text-yellow-500 px-1 rounded">
        ?
      </div>
    )}
  </Flex>
);

interface DAGViewerProps {
  dag: DAGDefinition;
  executions?: PipelineStepExecution[];
  selectedStepId?: string;
  onStepSelect?: (step: PipelineStep) => void;
}

export const DAGViewer: React.FC<DAGViewerProps> = ({
  dag,
  executions,
  selectedStepId,
  onStepSelect,
}) => {
  // Build execution order (levels)
  const getLevels = (): PipelineStep[][] => {
    const levels: PipelineStep[][] = [];
    const processed = new Set<string>();
    const stepMap = new Map(dag.steps.map((s) => [s.id, s]));

    // Find steps with no dependencies
    const getReadySteps = () =>
      dag.steps.filter(
        (step) =>
          !processed.has(step.id) &&
          step.depends_on.every((dep) => processed.has(dep))
      );

    while (processed.size < dag.steps.length) {
      const ready = getReadySteps();
      if (ready.length === 0) break;
      levels.push(ready);
      ready.forEach((step) => processed.add(step.id));
    }

    return levels;
  };

  const levels = getLevels();
  const executionMap = new Map(executions?.map((e) => [e.step_id, e]));

  // Find parallel steps (steps in the same level)
  const getParallelSteps = (step: PipelineStep, level: PipelineStep[]): string[] => {
    if (level.length <= 1) return [];
    return level.filter((s) => s.id !== step.id).map((s) => s.id);
  };

  return (
    <Box className="bg-[#0D0D0D] rounded-lg border border-[#1F1F1F] p-6 overflow-auto">
      {/* Start node */}
      <Flex justify="center" className="mb-2">
        <Flex
          align="center"
          justify="center"
          className="w-12 h-12 rounded-full bg-green-500/20 border-2 border-green-500"
        >
          <span className="text-green-500 font-bold text-sm">START</span>
        </Flex>
      </Flex>

      {/* Levels */}
      {levels.map((level, levelIndex) => (
        <React.Fragment key={levelIndex}>
          {/* Connection lines */}
          <Flex justify="center">
            {level.length === 1 ? (
              <ConnectionLine hasCondition={!!level[0].condition} />
            ) : (
              <Flex direction="column" align="center">
                {/* Parallel split */}
                <div className="w-0.5 h-3 bg-[#3F3F3F]" />
                <Flex align="center" className="relative">
                  <div
                    className="h-0.5 bg-purple-500/50"
                    style={{ width: `${level.length * 160}px` }}
                  />
                </Flex>
                <Flex justify="center" gap="4">
                  {level.map((_, i) => (
                    <div key={i} className="w-0.5 h-3 bg-purple-500/50 mx-[70px]" />
                  ))}
                </Flex>
              </Flex>
            )}
          </Flex>

          {/* Step nodes */}
          <Flex justify="center" gap="4" className="my-2">
            {level.map((step) => (
              <StepNode
                key={step.id}
                step={step}
                execution={executionMap.get(step.id)}
                isFirst={levelIndex === 0}
                isLast={levelIndex === levels.length - 1}
                parallelWith={getParallelSteps(step, level)}
                onSelect={onStepSelect}
                isSelected={selectedStepId === step.id}
              />
            ))}
          </Flex>

          {/* Merge lines for parallel */}
          {level.length > 1 && levelIndex < levels.length - 1 && (
            <Flex justify="center">
              <Flex direction="column" align="center">
                <Flex justify="center" gap="4">
                  {level.map((_, i) => (
                    <div key={i} className="w-0.5 h-3 bg-purple-500/50 mx-[70px]" />
                  ))}
                </Flex>
                <Flex align="center" className="relative">
                  <div
                    className="h-0.5 bg-purple-500/50"
                    style={{ width: `${level.length * 160}px` }}
                  />
                </Flex>
                <div className="w-0.5 h-3 bg-[#3F3F3F]" />
              </Flex>
            </Flex>
          )}
        </React.Fragment>
      ))}

      {/* End node */}
      <Flex justify="center" className="mt-2">
        <ConnectionLine />
      </Flex>
      <Flex justify="center">
        <Flex
          align="center"
          justify="center"
          className="w-12 h-12 rounded-full bg-red-500/20 border-2 border-red-500"
        >
          <span className="text-red-500 font-bold text-sm">END</span>
        </Flex>
      </Flex>

      {/* Legend */}
      <Flex gap="4" justify="center" className="mt-6 pt-4 border-t border-[#1F1F1F]">
        <Flex align="center" gap="1" className="text-[10px] text-gray-500">
          <ClockCircleOutlined /> Pending
        </Flex>
        <Flex align="center" gap="1" className="text-[10px] text-blue-500">
          <LoadingOutlined /> Running
        </Flex>
        <Flex align="center" gap="1" className="text-[10px] text-green-500">
          <CheckCircleOutlined /> Completed
        </Flex>
        <Flex align="center" gap="1" className="text-[10px] text-gray-400">
          <MinusCircleOutlined /> Skipped
        </Flex>
        <Flex align="center" gap="1" className="text-[10px] text-red-500">
          <CloseCircleOutlined /> Failed
        </Flex>
      </Flex>
    </Box>
  );
};

export default DAGViewer;
