import { Box, Flex } from "@radix-ui/themes";
import { Drawer, Tag } from "antd";
import React from "react";
import { PipelineStep, PipelineStepExecution } from "src/stores/useBudPipeline";

interface StepDetailDrawerProps {
  step: PipelineStep | null;
  execution?: PipelineStepExecution;
  onClose: () => void;
}

const StepDetailDrawer: React.FC<StepDetailDrawerProps> = ({ step, execution, onClose }) => {
  if (!step) return null;

  return (
    <Drawer
      title={step.name}
      open={!!step}
      onClose={onClose}
      width={400}
      className="bg-[#0D0D0D]"
      styles={{
        header: { backgroundColor: "#0D0D0D", borderBottom: "1px solid #1F1F1F" },
        body: { backgroundColor: "#0D0D0D" },
      }}
    >
      <Box className="space-y-4">
        <Box className="p-3 rounded bg-[#1A1A1A] border border-[#2F3035]">
          <div className="text-gray-500 text-xs mb-2">Step Details</div>
          <Flex direction="column" gap="2">
            <Flex justify="between">
              <span className="text-gray-400 text-sm">ID</span>
              <span className="text-white text-sm font-mono">{step.id}</span>
            </Flex>
            <Flex justify="between">
              <span className="text-gray-400 text-sm">Action</span>
              <Tag className="bg-[#252525] border-0 text-[#B3B3B3]">{step.action}</Tag>
            </Flex>
            {step.timeout_seconds && (
              <Flex justify="between">
                <span className="text-gray-400 text-sm">Timeout</span>
                <span className="text-white text-sm">{step.timeout_seconds}s</span>
              </Flex>
            )}
            {step.on_failure && (
              <Flex justify="between">
                <span className="text-gray-400 text-sm">On Failure</span>
                <Tag
                  className={`border-0 ${
                    step.on_failure === "continue"
                      ? "bg-yellow-500/20 text-yellow-500"
                      : "bg-red-500/20 text-red-500"
                  }`}
                >
                  {step.on_failure}
                </Tag>
              </Flex>
            )}
          </Flex>
        </Box>

        {step.depends_on && step.depends_on.length > 0 && (
          <Box className="p-3 rounded bg-[#1A1A1A] border border-[#2F3035]">
            <div className="text-gray-500 text-xs mb-2">Dependencies</div>
            <Flex gap="2" wrap="wrap">
              {(step.depends_on || []).map((dep) => (
                <Tag key={dep} className="bg-[#252525] border-0 text-[#B3B3B3]">
                  {dep}
                </Tag>
              ))}
            </Flex>
          </Box>
        )}

        {step.condition && (
          <Box className="p-3 rounded bg-yellow-500/5 border border-yellow-500/20">
            <div className="text-yellow-500 text-xs mb-2">Condition</div>
            <code className="text-yellow-400 text-sm bg-[#0D0D0D] px-2 py-1 rounded block">
              {step.condition}
            </code>
          </Box>
        )}

        <Box className="p-3 rounded bg-[#1A1A1A] border border-[#2F3035]">
          <div className="text-gray-500 text-xs mb-2">Parameters</div>
          <pre className="text-[11px] text-gray-400 bg-[#0D0D0D] p-2 rounded overflow-auto max-h-60">
            {JSON.stringify(step.params, null, 2)}
          </pre>
        </Box>

        {execution && (
          <Box
            className={`p-3 rounded border ${
              execution.status === "completed"
                ? "bg-green-500/5 border-green-500/20"
                : execution.status === "failed"
                ? "bg-red-500/5 border-red-500/20"
                : execution.status === "running"
                ? "bg-blue-500/5 border-blue-500/20"
                : "bg-gray-500/5 border-gray-500/20"
            }`}
          >
            <div className="text-gray-500 text-xs mb-2">Execution Status</div>
            <Flex direction="column" gap="2">
              <Flex justify="between">
                <span className="text-gray-400 text-sm">Status</span>
                <Tag
                  className={`border-0 ${
                    execution.status === "completed"
                      ? "bg-green-500/20 text-green-500"
                      : execution.status === "failed"
                      ? "bg-red-500/20 text-red-500"
                      : execution.status === "running"
                      ? "bg-blue-500/20 text-blue-500"
                      : "bg-gray-500/20 text-gray-500"
                  }`}
                >
                  {execution.status}
                </Tag>
              </Flex>
              {execution.started_at && (
                <Flex justify="between">
                  <span className="text-gray-400 text-sm">Started</span>
                  <span className="text-white text-sm">
                    {new Date(execution.started_at).toLocaleTimeString()}
                  </span>
                </Flex>
              )}
              {execution.completed_at && (
                <Flex justify="between">
                  <span className="text-gray-400 text-sm">Completed</span>
                  <span className="text-white text-sm">
                    {new Date(execution.completed_at).toLocaleTimeString()}
                  </span>
                </Flex>
              )}
            </Flex>

            {execution.error && (
              <Box className="mt-2 p-2 rounded bg-red-500/10">
                <span className="text-red-400 text-xs">{execution.error}</span>
              </Box>
            )}

            {Object.keys(execution.outputs).length > 0 && (
              <Box className="mt-2">
                <div className="text-gray-500 text-xs mb-1">Outputs</div>
                <pre className="text-[10px] text-gray-400 bg-[#0D0D0D] p-2 rounded overflow-auto max-h-40">
                  {JSON.stringify(execution.outputs, null, 2)}
                </pre>
              </Box>
            )}
          </Box>
        )}
      </Box>
    </Drawer>
  );
};

export default StepDetailDrawer;
