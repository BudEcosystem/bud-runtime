"use client";
import { Box, Flex } from "@radix-ui/themes";
import { useEffect, useState, useMemo } from "react";
import React from "react";
import { useRouter } from "next/router";
import DashBoardLayout from "../../layout";
import {
  Text_11_400_808080,
  Text_12_400_6A6E76,
  Text_13_400_B3B3B3,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import { useLoader } from "src/context/appContext";
import {
  ArrowLeftOutlined,
  PlayCircleOutlined,
  EditOutlined,
  DeleteOutlined,
  HistoryOutlined,
  CodeOutlined,
  ApartmentOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { useBudPipeline, PipelineStep, PipelineStepExecution, DAGDefinition } from "src/stores/useBudPipeline";
import { useCluster } from "src/hooks/useCluster";
import { useModels } from "src/hooks/useModels";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import { useProjects } from "src/hooks/useProjects";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import StepDetailDrawer from "@/components/pipelineEditor/components/StepDetailDrawer";
import { Button, Tabs, Tag, Modal, Form, Input, InputNumber, Switch, Select, Empty, Table, message } from "antd";
import { DAGViewer, ExecutionTimeline, PipelineEditor, PipelineTriggersPanel } from "@/components/pipelineEditor";
import { formatDistanceToNow } from "date-fns";
import { nanoid } from "nanoid";

const { TabPane } = Tabs;

// Execute pipeline modal
const ExecuteWorkflowModal: React.FC<{
  open: boolean;
  onClose: () => void;
  onExecute: (params: Record<string, any>) => void;
  parameters: Array<{
    name: string;
    type: string;
    description?: string;
    default?: any;
    required?: boolean;
  }>;
}> = ({ open, onClose, onExecute, parameters }) => {
  const [form] = Form.useForm();

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      onExecute(values);
      form.resetFields();
      onClose();
    });
  };

  return (
    <Modal
      title="Execute Pipeline"
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      okText="Execute"
      className="dark-modal"
    >
      <Form form={form} layout="vertical" className="mt-4">
        {parameters.map((param) => (
          <Form.Item
            key={param.name}
            name={param.name}
            label={
              <span className="text-gray-300">
                {param.name}
                {param.required && <span className="text-red-500 ml-1">*</span>}
              </span>
            }
            rules={[{ required: param.required, message: `${param.name} is required` }]}
            initialValue={param.default}
            tooltip={param.description}
          >
            {param.type === "boolean" ? (
              <Switch />
            ) : param.type === "integer" ? (
              <InputNumber className="w-full" />
            ) : (
              <Input placeholder={`Enter ${param.name}`} />
            )}
          </Form.Item>
        ))}
        {parameters.length === 0 && (
          <div className="text-gray-500 text-center py-4">
            This pipeline has no parameters
          </div>
        )}
      </Form>
    </Modal>
  );
};

const WorkflowDetail = () => {
  const router = useRouter();
  const { id } = router.query;
  const { showLoader, hideLoader } = useLoader();
  const {
    selectedWorkflow,
    getWorkflow,
    executions,
    getExecutions,
    selectedExecution,
    executeWorkflow,
    updateWorkflow,
    clearSelection,
  } = useBudPipeline();

  const { clusters, getClusters } = useCluster();
  const { models, getGlobalModels } = useModels();
  const { providers, getProviders } = useCloudProviders();
  const { projects, getProjects } = useProjects();

  const [activeTab, setActiveTab] = useState("dag");
  const [selectedStep, setSelectedStep] = useState<PipelineStep | null>(null);
  const [executeModalOpen, setExecuteModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedDag, setEditedDag] = useState<DAGDefinition | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [loadingDataSources, setLoadingDataSources] = useState<Set<string>>(new Set());
  const { openDrawer } = useDrawer();

  const sortedExecutions = useMemo(
    () =>
      executions
        .filter((exec) => exec?.execution_id)
        .slice()
        .sort((a, b) => {
          const aTime = a?.started_at ? new Date(a.started_at).getTime() : 0;
          const bTime = b?.started_at ? new Date(b.started_at).getTime() : 0;
          return bTime - aTime;
        }),
    [executions]
  );

  // Transform clusters, models, projects, and providers to SelectOption format for WorkflowEditor
  const dataSources = useMemo(() => ({
    clusters: clusters.map((c) => ({
      label: c.name,
      value: c.id,
    })),
    models: models.map((m) => ({
      label: m.name,
      value: m.id,
    })),
    projects: projects.map((p: any) => ({
      label: p.project?.name || p.name || "",
      value: p.project?.id || p.id || "",
    })),
    providers: providers.map((p) => ({
      label: p.name,
      value: p.id,
    })),
  }), [clusters, models, projects, providers]);

  // Fetch clusters, models, projects, and providers when entering edit mode
  useEffect(() => {
    if (isEditing) {
      const loadingSet = new Set<string>();

      if (clusters.length === 0) {
        loadingSet.add("clusters");
      }
      if (models.length === 0) {
        loadingSet.add("models");
      }
      if (projects.length === 0) {
        loadingSet.add("projects");
      }
      if (providers.length === 0) {
        loadingSet.add("providers");
      }

      if (loadingSet.size > 0) {
        setLoadingDataSources(loadingSet);

        // Fetch data sources in parallel
        const fetchPromises: Promise<void>[] = [];

        if (clusters.length === 0) {
          fetchPromises.push(
            getClusters({ page: 1, limit: 100 }).then(() => {
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("clusters");
                return next;
              });
            })
          );
        }

        if (models.length === 0) {
          // getGlobalModels is async but returns void, so we wrap it
          // Use table_source: "model" to fetch only local/repository models
          // (excludes cloud provider models like grok, gemini, claude)
          fetchPromises.push(
            (async () => {
              await getGlobalModels({ page: 1, limit: 100, table_source: "model" });
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("models");
                return next;
              });
            })()
          );
        }

        if (projects.length === 0) {
          fetchPromises.push(
            (async () => {
              await getProjects(1, 100);
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("projects");
                return next;
              });
            })()
          );
        }

        if (providers.length === 0) {
          fetchPromises.push(
            (async () => {
              await getProviders(1, 100);
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("providers");
                return next;
              });
            })()
          );
        }

        Promise.all(fetchPromises).finally(() => {
          setLoadingDataSources(new Set());
        });
      }
    }
  }, [isEditing]);

  useEffect(() => {
    if (id && typeof id === "string") {
      showLoader();
      Promise.all([getWorkflow(id), getExecutions(id)]).finally(() => hideLoader());
    }
    return () => clearSelection();
  }, [id]);

  const handleExecute = async (params: Record<string, any>) => {
    if (selectedWorkflow) {
      await executeWorkflow(selectedWorkflow.id, params);
      await getExecutions(selectedWorkflow.id);
    }
  };

  const handleOpenExecutionDetails = (executionId: string) => {
    if (!selectedWorkflow) return;
    openDrawer("pipeline-execution-details", {
      executionId,
      workflow: selectedWorkflow,
    });
  };

  const handleStepSelect = (step: PipelineStep) => {
    setSelectedStep(step);
  };

  const getStepExecution = (stepId: string): PipelineStepExecution | undefined => {
    if (!selectedExecution) return undefined;
    return selectedExecution.steps.find((s) => s.step_id === stepId);
  };

  // Edit mode handlers
  const handleStartEditing = () => {
    setEditedDag(selectedWorkflow.dag ? { ...selectedWorkflow.dag } : {
      name: selectedWorkflow.name || "Untitled Pipeline",
      steps: [],
      parameters: []
    });
    setIsEditing(true);
    setActiveTab("dag");
  };

  const handleCancelEditing = () => {
    setEditedDag(null);
    setIsEditing(false);
  };

  const handleSaveEditing = async () => {
    if (editedDag && id && typeof id === "string") {
      try {
        setIsSaving(true);
        const result = await updateWorkflow(id, editedDag);
        if (result) {
          message.success("Pipeline updated successfully");
          setIsEditing(false);
          setEditedDag(null);
          // Refresh the pipeline to get the updated data
          await getWorkflow(id);
        } else {
          message.error("Failed to save pipeline changes");
        }
      } catch (error) {
        message.error("Failed to save pipeline changes");
        console.error("Save pipeline error:", error);
      } finally {
        setIsSaving(false);
      }
    }
  };

  const handleDagChange = (updatedDag: DAGDefinition) => {
    setEditedDag(updatedDag);
  };

  const handleAddStep = (action: string) => {
    if (!editedDag) return;

    // Find the last step to connect to by default
    // If there are existing steps, connect to the most recently added one
    // Otherwise, the step will connect from Start (depends_on: [])
    const existingSteps = editedDag.steps;
    const lastStep = existingSteps.length > 0 ? existingSteps[existingSteps.length - 1] : null;

    const newStep: PipelineStep = {
      id: `step_${nanoid(5)}`,
      name: `New ${action} Step`,
      action,
      params: {},
      depends_on: lastStep ? [lastStep.id] : [],
    };

    setEditedDag({
      ...editedDag,
      steps: [...editedDag.steps, newStep],
    });

    message.info(`Added new ${action} step`);
  };

  const handleStepUpdate = (stepId: string, updates: Partial<PipelineStep>) => {
    if (!editedDag) return;

    setEditedDag({
      ...editedDag,
      steps: editedDag.steps.map((step) =>
        step.id === stepId ? { ...step, ...updates } : step
      ),
    });
  };

  const handleStepDelete = (stepId: string) => {
    if (!editedDag) return;

    // Remove the step and update dependencies
    const updatedSteps = editedDag.steps
      .filter((step) => step.id !== stepId)
      .map((step) => ({
        ...step,
        depends_on: (step.depends_on || []).filter((dep) => dep !== stepId),
      }));

    setEditedDag({
      ...editedDag,
      steps: updatedSteps,
    });

    message.success("Step deleted");
  };

  const handleNodeClick = (nodeType: string, nodeId: string, nodeData: any) => {
    // In edit mode, the ActionConfigPanel handles node selection
    // Only open the detail drawer in read-only mode
    if (isEditing) return;

    // Find the step in the DAG
    const step = selectedWorkflow.dag?.steps?.find((s) => s.id === nodeId || s.id === nodeData?.stepId);
    if (step) {
      setSelectedStep(step);
    }
  };

  if (!selectedWorkflow) {
    return (
      <DashBoardLayout>
        <Box className="boardPageView">
          <Flex align="center" justify="center" className="h-[60vh]">
            <Empty description="Pipeline not found" />
          </Flex>
        </Box>
      </DashBoardLayout>
    );
  }

  return (
    <DashBoardLayout>
      <Box className="boardPageView">
        {/* Header */}
        <Flex
          justify="between"
          align="center"
          className="px-6 py-4 border-b border-[#1F1F1F] bg-[#0D0D0D]"
        >
          <Flex align="center" gap="4">
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => router.push("/pipelines")}
              className="text-gray-400 hover:text-white"
            />
            <Box>
              <Flex align="center" gap="2">
                <Text_17_600_FFFFFF>{selectedWorkflow.name}</Text_17_600_FFFFFF>
                <Tag
                  className={`border-0 ${
                    selectedWorkflow.status === "active"
                      ? "bg-green-500/20 text-green-500"
                      : selectedWorkflow.status === "draft"
                      ? "bg-yellow-500/20 text-yellow-500"
                      : "bg-gray-500/20 text-gray-500"
                  }`}
                >
                  {selectedWorkflow.status}
                </Tag>
              </Flex>
              <Text_12_400_6A6E76>
                {selectedWorkflow.step_count} steps • {selectedWorkflow.execution_count || 0} executions
              </Text_12_400_6A6E76>
            </Box>
          </Flex>
          <Flex gap="2">
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setExecuteModalOpen(true)}
            >
              Execute
            </Button>
            {isEditing ? (
              <>
                <Button onClick={handleCancelEditing} disabled={isSaving}>Cancel</Button>
                <Button type="primary" onClick={handleSaveEditing} loading={isSaving}>
                  Save Changes
                </Button>
              </>
            ) : (
              <>
                <Button icon={<EditOutlined />} onClick={handleStartEditing}>
                  Edit
                </Button>
                <Button icon={<DeleteOutlined />} danger>
                  Delete
                </Button>
              </>
            )}
          </Flex>
        </Flex>

        {/* Content */}
        <Box className="p-6">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            className="workflow-tabs"
            items={[
              {
                key: "dag",
                label: (
                  <Flex align="center" gap="2">
                    <ApartmentOutlined />
                    <span>{isEditing ? "Visual Editor" : "DAG View"}</span>
                  </Flex>
                ),
                children: (
                  <Box
                    className="-mx-5 -my-4"
                    style={{ height: "calc(100vh - 150px)", minHeight: "500px" }}
                  >
                    <PipelineEditor
                      dag={isEditing && editedDag ? editedDag : (selectedWorkflow.dag || {
                        name: selectedWorkflow.name || "Untitled Pipeline",
                        steps: [],
                        parameters: []
                      })}
                      onNodeClick={handleNodeClick}
                      onAddStep={isEditing ? handleAddStep : undefined}
                      onSave={isEditing ? handleDagChange : undefined}
                      onStepUpdate={isEditing ? handleStepUpdate : undefined}
                      onStepDelete={isEditing ? handleStepDelete : undefined}
                      readonly={!isEditing}
                      dataSources={dataSources}
                      loadingDataSources={loadingDataSources}
                    />
                  </Box>
                ),
              },
              {
                key: "executions",
                label: (
                  <Flex align="center" gap="2">
                    <HistoryOutlined />
                    <span>Executions ({executions.length})</span>
                  </Flex>
                ),
                children: (
                  <Box className="mt-4">
                    {executions.length > 0 ? (
                      <>
                        <Table
                          rowKey="execution_id"
                          pagination={false}
                          dataSource={sortedExecutions}
                          className="workflow-executions-table"
                          columns={[
                            {
                              title: "Run #",
                              key: "run_number",
                              render: (_: unknown, __: any, index: number) => (
                                <Text_11_400_808080>
                                  #{sortedExecutions.length - index}
                                </Text_11_400_808080>
                              ),
                            },
                            {
                              title: "Execution ID",
                              dataIndex: "execution_id",
                              key: "execution_id",
                              render: (value: string) => (
                                <Text_11_400_808080>{value}</Text_11_400_808080>
                              ),
                            },
                            {
                              title: "Status",
                              dataIndex: "status",
                              key: "status",
                              render: (status: string) => {
                                const normalizedStatus = status?.toUpperCase();
                                return (
                                  <Tag
                                    className={`border-0 text-[10px] ${
                                      normalizedStatus === "COMPLETED"
                                        ? "bg-green-500/20 text-green-500"
                                        : normalizedStatus === "FAILED"
                                        ? "bg-red-500/20 text-red-500"
                                        : normalizedStatus === "RUNNING"
                                        ? "bg-blue-500/20 text-blue-500"
                                        : normalizedStatus === "PENDING"
                                        ? "bg-yellow-500/20 text-yellow-500"
                                        : "bg-gray-500/20 text-gray-500"
                                    }`}
                                  >
                                    {status?.toLowerCase()}
                                  </Tag>
                                );
                              },
                            },
                            {
                              title: "Started",
                              dataIndex: "started_at",
                              key: "started_at",
                              render: (value: string) => (
                                <Text_11_400_808080>
                                  {value
                                    ? formatDistanceToNow(new Date(value), { addSuffix: true })
                                    : "—"}
                                </Text_11_400_808080>
                              ),
                            },
                            {
                              title: "Completed",
                              dataIndex: "completed_at",
                              key: "completed_at",
                              render: (value: string) => (
                                <Text_11_400_808080>
                                  {value
                                    ? formatDistanceToNow(new Date(value), { addSuffix: true })
                                    : "—"}
                                </Text_11_400_808080>
                              ),
                            },
                            {
                              title: "",
                              key: "actions",
                              align: "right",
                              render: (_: unknown, record: any) => (
                                <PrimaryButton
                                  classNames="min-w-[3.4rem]"
                                  onClick={() => handleOpenExecutionDetails(record.execution_id)}
                                  text="View"
                                  style={{
                                    height: "1.4rem",
                                    paddingLeft: "0.45rem",
                                    paddingRight: "0.45rem",
                                  }}
                                  textStyle={{
                                    fontSize: "0.65rem",
                                  }}
                                />
                              ),
                            },
                          ]}
                        />
                      </>
                    ) : (
                      <Flex
                        align="center"
                        justify="center"
                        className="h-[400px] bg-[#0D0D0D] rounded-lg border border-[#1F1F1F]"
                      >
                        <Empty
                          description="No executions yet"
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                        >
                          <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            onClick={() => setExecuteModalOpen(true)}
                          >
                            Run First Execution
                          </Button>
                        </Empty>
                      </Flex>
                    )}
                  </Box>
                ),
              },
              {
                key: "json",
                label: (
                  <Flex align="center" gap="2">
                    <CodeOutlined />
                    <span>JSON Definition</span>
                  </Flex>
                ),
                children: (
                  <Box className="mt-4 bg-[#0D0D0D] rounded-lg border border-[#1F1F1F] p-4">
                    <pre className="text-[11px] text-gray-400 overflow-auto max-h-[600px]">
                      {JSON.stringify(selectedWorkflow.dag || { steps: [], parameters: [] }, null, 2)}
                    </pre>
                  </Box>
                ),
              },
              {
                key: "triggers",
                label: (
                  <Flex align="center" gap="2">
                    <ClockCircleOutlined />
                    <span>Triggers</span>
                  </Flex>
                ),
                children: (
                  <Box className="mt-4">
                    <PipelineTriggersPanel workflowId={selectedWorkflow.id} />
                  </Box>
                ),
              },
            ]}
          />
        </Box>
      </Box>

      {/* Step detail drawer */}
      <StepDetailDrawer
        step={selectedStep}
        execution={selectedStep ? getStepExecution(selectedStep.id) : undefined}
        onClose={() => setSelectedStep(null)}
      />

      {/* Execute modal */}
      <ExecuteWorkflowModal
        open={executeModalOpen}
        onClose={() => setExecuteModalOpen(false)}
        onExecute={handleExecute}
        parameters={selectedWorkflow.dag?.parameters || []}
      />
    </DashBoardLayout>
  );
};

export default WorkflowDetail;
