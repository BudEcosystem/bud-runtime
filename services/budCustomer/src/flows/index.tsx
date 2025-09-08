import React from "react";
import CreateBatchJob from "./BatchJob/CreateBatchJob";
import CreateBatchJobSuccess from "./BatchJob/CreateBatchJobSuccess";
import NewProject from "./NewProject";
import EditProject from "./EditProject";
// import DeleteProject from "./DeleteProject"; // Removed - now using notification warning approach
import AddNewKey from "./ApiKeys/AddNewKey";
import ApiKeySuccess from "./ApiKeys/ApiKeySuccess";
import ViewApiKey from "./ApiKeys/ViewApiKey";
import ProjectSuccess from "./Projects/ProjectSuccess";
import ProjectEditSuccess from "./Projects/ProjectEditSuccess";
import EditApiKey from "./ApiKeys/EditApiKey";
import ViewModelDetails from "./ViewModelDetails";
import ViewProjectDetails from "./ViewProjectDetails";

// Placeholder component factory
const createPlaceholderComponent = (name: string) => {
  const Component: React.FC = () => {
    return <div>Placeholder for: {name}</div>;
  };
  Component.displayName = name;
  return Component;
};

// List of all step component names used in drawerFlows
const stepComponentNames = [
  "add-new-cloud-provider",
  "add-cloud-credential-form",
  "cloud-credentials-success",
  "new-project",
  "invite-members",
  "project-success",
  "invite-success",
  "deploy-model",
  "deploy-model-credential-select",
  "deploy-model-template",
  "deploy-model-specification",
  "deploy-cluster-status",
  "deploy-model-choose-cluster",
  "deploy-model-auto-scaling",
  "deploy-model-status",
  "deploy-model-success",
  "modality-source",
  "model-source",
  "cloud-providers",
  "model-list",
  "add-model",
  "model-success",
  "model-evaluations",
  "add-local-model",
  "select-or-add-credentials",
  "extracting-model",
  "security-scan-status",
  "scan-completed",
  "select-model-evaluations",
  "select-cluster-evaluations",
  "select-credentials",
  "evaluation-information",
  "evaluation-results",
  "run-model-success",
  "stop-warning",
  "edit-model",
  "add-cluster-select-source",
  "add-cluster-select-provider",
  "choose-cloud-credential",
  "configure-cluster-details",
  "add-cluster",
  "create-cluster-status",
  "create-cluster-success",
  "edit-cluster",
  "view-model-details",
  "view-project-details",
  "edit-project",
  "add-members",
  "add-worker",
  "add-worker-cluster-config-status",
  "add-worker-cluster-configuration",
  "add-worker-deploy-status",
  "add-worker-success",
  "worker-details",
  "use-model",
  "delete-cluster",
  "delete-project",
  "delete-endpoint-status",
  "delete-cluster-status",
  "delete-worker-status",
  "add-credentials-choose-provider",
  "add-credentials-form",
  "credentials-success",
  "view-credentials",
  "view-project-credentials",
  "add-new-key",
  "edit-project-credential",
  "license-Details",
  "derived-model-list",
  "cluster-event",
  "view-user",
  "edit-user",
  "reset-password",
  "add-user",
  "add-user-details",
  "model_benchmark",
  "Datasets",
  "Configuration",
  "Select-Cluster",
  "Select-Nodes",
  "Select-Model",
  "model_benchmark-credential-select",
  "Benchmark-Configuration",
  "simulate-run",
  "Benchmarking-Progress",
  "Benchmarking-Finished",
  "quantization-detail",
  "quantization-method",
  "advanced-settings",
  "quantization-simulation-status",
  "quantization-select-cluster",
  "quantization-deployment-status",
  "quantization-result",
  "select-evaluation-type",
  "select-use-case",
  "additional-settings",
  "select-model-for-evaluation",
  "model-quantisation",
  "select-hardware",
  "hardware-pecifications",
  "simulation-details",
  "add-adapter-select-model",
  "add-adapter-detail",
  "add-adapter-status",
  "add-adapter-result",
  "delete-adapter-status",
  "edit-user-profile",
  "create-route-data",
  "select-endpoints-route",
  "select-fallback-deployment",
  "new-experiment",
  "new-evaluation",
  "select-model-new-evaluation",
  "select-traits",
  "select-evaluation",
  "evaluation-summary",
  "create-batch-job",
  "create-batch-job-success",
  "api-key-success",
  "project-success",
  "project-edit-success",
  "edit-api-key",
];

// Create StepComponents object with placeholder components
export const StepComponents = stepComponentNames.reduce(
  (acc, name) => {
    acc[name] = createPlaceholderComponent(name);
    return acc;
  },
  {} as Record<string, React.FC>,
);

// Override with actual components
StepComponents["create-batch-job"] = CreateBatchJob;
StepComponents["create-batch-job-success"] = CreateBatchJobSuccess;
StepComponents["new-project"] = NewProject;
StepComponents["edit-project"] = EditProject;
// StepComponents["delete-project"] = DeleteProject; // Removed - now using notification warning approach
StepComponents["add-new-key"] = AddNewKey;
StepComponents["api-key-success"] = ApiKeySuccess;
StepComponents["project-success"] = ProjectSuccess;
StepComponents["project-edit-success"] = ProjectEditSuccess;
StepComponents["view-api-key"] = ViewApiKey;
StepComponents["edit-api-key"] = EditApiKey;
StepComponents["view-model-details"] = ViewModelDetails;
StepComponents["view-project-details"] = ViewProjectDetails;

export type StepComponentsType = keyof typeof StepComponents;
