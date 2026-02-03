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
  HistoryOutlined,
  ApartmentOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { useBudPipeline, PipelineStep, PipelineStepExecution, DAGDefinition } from "src/stores/useBudPipeline";
import { useCluster } from "src/hooks/useCluster";
import { useModels } from "src/hooks/useModels";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import { useProjects } from "src/hooks/useProjects";
import { useProprietaryCredentials } from "src/stores/useProprietaryCredentials";
import { useEndPoints } from "src/hooks/useEndPoint";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import StepDetailDrawer from "@/components/pipelineEditor/components/StepDetailDrawer";
import { Button, Tag, Empty, Table } from "antd";
import { successToast, errorToast } from "@/components/toast";
import { PipelineEditor, PipelineTriggersPanel } from "@/components/pipelineEditor";
import { formatDistanceToNow } from "date-fns";
import { nanoid } from "nanoid";

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
  const { credentials: proprietaryCredentials, getCredentials: getProprietaryCredentials } = useProprietaryCredentials();
  const { endPoints, getEndPoints } = useEndPoints();

  const [activeTab, setActiveTab] = useState("dag");
  const [selectedStep, setSelectedStep] = useState<PipelineStep | null>(null);
  const [editedDag, setEditedDag] = useState<DAGDefinition | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Always in edit mode
  const isEditing = true;
  const [loadingDataSources, setLoadingDataSources] = useState<Set<string>>(new Set());
  const [isExecuting, setIsExecuting] = useState(false);
  const { openDrawer } = useDrawer();
  const { contextHolder, openConfirm } = useConfirmAction();

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

  // Transform clusters, models, projects, providers, credentials, and endpoints to SelectOption format for WorkflowEditor
  // Note: clusters use cluster_id (budcluster UUID) as value, not id (budapp UUID),
  // to match what deploy-workflow endpoint expects
  const dataSources = useMemo(() => ({
    clusters: clusters.map((c) => ({
      label: c.name,
      value: c.cluster_id,
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
    credentials: proprietaryCredentials.map((c) => ({
      label: `${c.name} (${c.type})`,
      value: c.id,
    })),
    endpoints: endPoints.map((e) => ({
      label: e.name || e.id || "",
      value: e.id || "",
    })),
  }), [clusters, models, projects, providers, proprietaryCredentials, endPoints]);

  // Fetch clusters, models, projects, providers, credentials, and endpoints when entering edit mode
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
      if (proprietaryCredentials.length === 0) {
        loadingSet.add("credentials");
      }
      if (endPoints.length === 0) {
        loadingSet.add("endpoints");
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

        if (proprietaryCredentials.length === 0) {
          fetchPromises.push(
            (async () => {
              await getProprietaryCredentials({ page: 1, limit: 100 });
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("credentials");
                return next;
              });
            })()
          );
        }

        if (endPoints.length === 0) {
          fetchPromises.push(
            (async () => {
              // Fetch all endpoints (no project filter needed for pipeline actions)
              await getEndPoints({ page: 1, limit: 100 });
              setLoadingDataSources(prev => {
                const next = new Set(prev);
                next.delete("endpoints");
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

  // Initialize editedDag when workflow loads
  useEffect(() => {
    if (selectedWorkflow?.dag) {
      setEditedDag({ ...selectedWorkflow.dag });
    } else if (selectedWorkflow) {
      setEditedDag({
        name: selectedWorkflow.name || "Untitled Pipeline",
        steps: [],
        parameters: []
      });
    }
  }, [selectedWorkflow]);

  // Check if pipeline can be executed (has at least one step)
  const canExecute = useMemo(() => {
    const dag = editedDag || selectedWorkflow?.dag;
    const stepCount = dag?.steps?.length ?? selectedWorkflow?.step_count ?? 0;
    return stepCount > 0;
  }, [editedDag, selectedWorkflow]);

  const handleExecute = async () => {
    if (selectedWorkflow) {
      // Frontend validation: check if pipeline has steps
      if (!canExecute) {
        errorToast("Cannot execute a pipeline with no steps");
        return;
      }

      setIsExecuting(true);
      // Get parameters from the current DAG (edited or original)
      const dag = editedDag || selectedWorkflow.dag;
      const params: Record<string, any> = {};
      // Populate params with default values from DAG parameters
      if (dag?.parameters) {
        for (const param of dag.parameters) {
          if (param.default !== undefined) {
            params[param.name] = param.default;
          }
        }
      }
      const result = await executeWorkflow(selectedWorkflow.id, params);
      await getExecutions(selectedWorkflow.id);
      setIsExecuting(false);
      if (result) {
        successToast("Pipeline execution started");
      } else {
        errorToast(useBudPipeline.getState().error || "Failed to execute pipeline");
      }
    }
  };

  const confirmExecute = () => {
    // Check if pipeline has steps before showing execute confirmation
    if (!canExecute) {
      openConfirm({
        message: "Cannot Execute Pipeline",
        description: "This pipeline has no steps. Add at least one step and click Save before executing.",
        cancelAction: () => {},
        cancelText: "Close",
        loading: false,
        key: "execute-pipeline-no-steps",
        okAction: () => setActiveTab("dag"),
        okText: "Go to Editor",
        type: "warning",
      });
      return;
    }

    openConfirm({
      message: `Execute "${selectedWorkflow?.name}"?`,
      description: "This will start a new execution of the pipeline with all configured steps.",
      cancelAction: () => {},
      cancelText: "Cancel",
      loading: isExecuting,
      key: "execute-pipeline",
      okAction: handleExecute,
      okText: "Execute",
      type: "warning",
    });
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

  // Save handler
  const handleSaveEditing = async () => {
    if (editedDag && id && typeof id === "string") {
      try {
        setIsSaving(true);
        const result = await updateWorkflow(id, editedDag);
        if (result) {
          successToast("Pipeline saved");
          // Refresh the pipeline to get the updated data
          await getWorkflow(id);
        } else {
          errorToast("Failed to save pipeline");
        }
      } catch (error) {
        errorToast("Failed to save pipeline");
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

    successToast("Step deleted");
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
      {contextHolder}
      <Box className="boardPageView">
        {/* Header with integrated tabs */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 16px',
            borderBottom: '1px solid #1F1F1F',
            backgroundColor: '#0D0D0D',
            gap: '16px',
          }}
        >
          {/* Left: Back button + Pipeline info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 1, minWidth: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => router.push("/pipelines")}
              className="text-gray-400 hover:text-white"
              style={{ flexShrink: 0, padding: '4px 8px' }}
            />
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#FFFFFF',
                }}>{selectedWorkflow.name}</span>
                <Tag
                  className={`border-0 text-[10px] ${
                    selectedWorkflow.status === "active"
                      ? "bg-green-500/20 text-green-500"
                      : selectedWorkflow.status === "draft"
                      ? "bg-yellow-500/20 text-yellow-500"
                      : "bg-gray-500/20 text-gray-500"
                  }`}
                  style={{ marginRight: 0, padding: '0 6px', lineHeight: '18px' }}
                >
                  {selectedWorkflow.status}
                </Tag>
              </div>
              <span style={{ fontSize: '11px', color: '#6A6E76', whiteSpace: 'nowrap' }}>
                {selectedWorkflow.step_count} steps • {selectedWorkflow.execution_count || 0} runs
              </span>
            </div>
          </div>

          {/* Center: Tab buttons */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
              borderRadius: '6px',
              padding: '3px',
              backgroundColor: '#1a1a1a',
              flexShrink: 0,
            }}
          >
            <button
              onClick={() => setActiveTab("dag")}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 14px',
                borderRadius: '4px',
                fontSize: '11px',
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor: activeTab === "dag" ? '#2a2a2a' : 'transparent',
                color: activeTab === "dag" ? '#fff' : '#6b7280',
              }}
            >
              <ApartmentOutlined style={{ fontSize: 11 }} />
              <span>Editor</span>
            </button>
            <button
              onClick={() => setActiveTab("executions")}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 14px',
                borderRadius: '4px',
                fontSize: '11px',
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor: activeTab === "executions" ? '#2a2a2a' : 'transparent',
                color: activeTab === "executions" ? '#fff' : '#6b7280',
              }}
            >
              <HistoryOutlined style={{ fontSize: 11 }} />
              <span>Runs</span>
            </button>
            <button
              onClick={() => setActiveTab("triggers")}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 14px',
                borderRadius: '4px',
                fontSize: '11px',
                border: 'none',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor: activeTab === "triggers" ? '#2a2a2a' : 'transparent',
                color: activeTab === "triggers" ? '#fff' : '#6b7280',
              }}
            >
              <ClockCircleOutlined style={{ fontSize: 11 }} />
              <span>Triggers</span>
            </button>
          </div>

          {/* Right: Action buttons */}
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={confirmExecute}
            >
              Execute
            </Button>
            <Button
              onClick={handleSaveEditing}
              loading={isSaving}
              className="pipeline-save-btn"
            >
              Save
            </Button>
            <style jsx global>{`
              .pipeline-save-btn {
                background-color: #22c55e !important;
                border-color: #22c55e !important;
                color: #fff !important;
              }
              .pipeline-save-btn:hover {
                background-color: #16a34a !important;
                border-color: #16a34a !important;
              }
            `}</style>
          </div>
        </div>

        {/* Content - Full height for DAG, padded for other tabs */}
        {activeTab === "dag" && (
          <Box style={{ height: "calc(100vh - 73px)", minHeight: "500px" }}>
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
        )}

        {activeTab === "executions" && (
          <Box className="p-6">
            {executions.length > 0 ? (
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
                    onClick={confirmExecute}
                  >
                    Run First Execution
                  </Button>
                </Empty>
              </Flex>
            )}
          </Box>
        )}

        {activeTab === "triggers" && (
          <Box className="p-6">
            <PipelineTriggersPanel workflowId={selectedWorkflow.id} />
          </Box>
        )}
      </Box>

      {/* Step detail drawer */}
      <StepDetailDrawer
        step={selectedStep}
        execution={selectedStep ? getStepExecution(selectedStep.id) : undefined}
        onClose={() => setSelectedStep(null)}
      />
    </DashBoardLayout>
  );
};

export default WorkflowDetail;
