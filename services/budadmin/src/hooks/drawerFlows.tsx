import {
  FormProgressStatus,
  FormProgressType,
} from "@/components/ui/bud/progress/FormProgress";
import { useProjects } from "./useProjects";
import { useModels } from "./useModels";
import { useWorkers } from "./useWorkers";
import { StepComponents } from "src/flows";
import { useEndPoints } from "./useEndPoint";
import { useDeployModel } from "src/stores/useDeployModel";
import ChooseCloudSource from "src/flows/Cluster/ChooseCloudSource";
import { create } from "domain";

export type DrawerStepType = {
  id: string;
  step: number;
  navigation: () => string[];
  component: React.FC;
  progress: FormProgressType[];
  properties?: any;
  confirmClose: boolean;
};

export type DrawerFlowType = {
  steps: DrawerStepType[];
  totalSteps: number;
  title: string;
  description: string;
};

// Flow For Cloud Providers -- add-new-cloud-provider"
const addNewCloudProvider: DrawerFlowType = {
  title: "Connect To Cloud",
  description: "Connect to a cloud provider",
  totalSteps: 2,
  steps: [
    {
      navigation: () => ["Cloud Providers", "Connect To Cloud"],
      id: "add-new-cloud-provider",
      step: 1,
      component: StepComponents["add-new-cloud-provider"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Add Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Cloud Providers", "Connect To Cloud"],
      id: "add-cloud-credential-form",
      step: 2,
      component: StepComponents["add-cloud-credential-form"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Add Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Cloud Providers", "Connect To Cloud"],
      id: "cloud-credentials-success",
      step: 3,
      component: StepComponents["cloud-credentials-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const newProject: DrawerFlowType = {
  title: "New Project",
  description: "Create a new project",
  totalSteps: 3,
  steps: [
    {
      navigation: () => ["Projects", "New Project"],
      id: "new-project",
      step: 1,
      component: StepComponents["new-project"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Project",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Invite Members",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Projects", "New Project"],
      id: "invite-members",
      step: 2,
      component: StepComponents["invite-members"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Project",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Invite Members",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Projects", "New Project"],
      id: "project-success",
      properties: {
        text: "Project Created Successfully",
      },
      step: 3,
      component: StepComponents["project-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Invite Members",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Projects", "New Project"],
      id: "invite-success",
      properties: {
        text: "Project Created and Invites Sent",
      },
      step: 3,
      component: StepComponents["invite-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Invite Members",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const deployModel: DrawerFlowType = {
  title: "Deployment",
  description: "Deployment Under Progress",
  totalSteps: 10,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model",
      component: StepComponents["deploy-model"],
      step: 1,
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Deployment Templates",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-credential-select",
      component: StepComponents["deploy-model-credential-select"],
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      step: 2,
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-hardware-mode",
      component: StepComponents["deploy-model-hardware-mode"],
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      step: 2,
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-template",
      confirmClose: true,
      step: 3,
      component: StepComponents["deploy-model-template"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-specification",
      step: 4,
      component: StepComponents["deploy-model-specification"],
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-cluster-status",
      confirmClose: true,
      step: 5,
      component: StepComponents["deploy-cluster-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-choose-cluster",
      component: StepComponents["deploy-model-choose-cluster"],
      confirmClose: true,
      step: 6,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.completed,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-configuration",
      step: 7,
      component: StepComponents["deploy-model-configuration"],
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.completed,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.completed,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-auto-scaling",
      component: StepComponents["deploy-model-auto-scaling"],
      confirmClose: true,
      step: 8,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.completed,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.completed,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-status",
      confirmClose: true,
      step: 9,
      component: StepComponents["deploy-model-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.completed,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.completed,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Status",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Deploy Model",
      ],
      id: "deploy-model-success",
      confirmClose: false,
      step: 10,
      component: StepComponents["deploy-model-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploy Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: " Select Deployment Templates",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Specification",
        },
        {
          status: FormProgressStatus.completed,
          title: "Finding Clusters",
        },
        {
          status: FormProgressStatus.completed,
          title: "Choose Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Deployment Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Auto Scaling",
        },
        {
          status: FormProgressStatus.completed,
          title: "Status",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
    },
  ],
};

const addModel: DrawerFlowType = {
  title: "Add Model",
  description: "Add a new model",
  totalSteps: 6,
  steps: [
    {
      navigation: () => ["Model", "Add Model"],
      id: "modality-source",
      component: StepComponents["modality-source"],
      step: 1,
      confirmClose: false,
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Modality",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
      ],
      // TODO Placeholder for the component
    },
    {
      navigation: () => ["Model", "Add Model"],
      id: "model-source",
      component: StepComponents["model-source"],
      step: 1,
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "",
        },
      ],
      // TODO Placeholder for the component
    },
  ],
};

const addModelCloudFlow: DrawerFlowType = {
  title: "Add Model",
  description: "Add a new model",
  totalSteps: 6,
  steps: [
    {
      navigation: () => ["Model", "New Model"],
      id: "cloud-providers",
      confirmClose: true,
      component: StepComponents["cloud-providers"],
      step: 2,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model List",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Run Evaluations",
          hidden: true,
        },
      ],
    },
    {
      navigation: () => ["Model", "New Model"],
      confirmClose: true,
      id: "model-list",
      component: StepComponents["model-list"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Model List",
        },

        {
          status: FormProgressStatus.notCompleted,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Run Evaluations",
          hidden: true,
        },
      ],
      step: 3,
    },
    {
      id: "add-model",
      navigation: () => ["Model", "New Model"],
      component: StepComponents["add-model"],
      confirmClose: true,
      step: 4,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model List",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Add Model",
        },

        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Run Evaluations",
          hidden: true,
        },
      ],
    },
    {
      id: "cloud-model-success",
      navigation: () => ["Model", "New Model"],
      component: StepComponents["model-success"],
      confirmClose: false,
      step: 5,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model List",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
    },
    {
      id: "model-evaluations",
      navigation: () => ["Model", "New Model"],
      component: StepComponents["model-evaluations"],
      confirmClose: true,
      step: 6,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cloud Providers",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model List",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Success",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Run Evaluations",
          hidden: true,
        },
      ],
    },
  ],
};

const addModelLocalFlow: DrawerFlowType = {
  title: "Add Model",
  description: "Add a new model",
  totalSteps: 5,
  steps: [
    {
      id: "add-local-model",
      component: StepComponents["add-local-model"],
      navigation: () => ["Model", "Add Model"],
      confirmClose: true,
      step: 2,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select or Add Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      id: "select-or-add-credentials",
      navigation: () => ["Model", "Add Model"],
      confirmClose: true,
      step: 3,
      component: StepComponents["select-or-add-credentials"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select or Add Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      id: "extracting-model-status",
      navigation: () => ["Model", "Add Model"],
      step: 4,
      confirmClose: true,
      component: StepComponents["extracting-model"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select or Add Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      id: "local-model-success",
      confirmClose: false,
      step: 5,
      navigation: () => ["Model", "Add Model"],
      component: StepComponents["model-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Add Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select or Add Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
    },
  ],
};

const documentModelFlow: DrawerFlowType = {
  title: "Select Document Model",
  description: "Select a document processing model",
  totalSteps: 4,
  steps: [
    {
      id: "document-model-list",
      component: StepComponents["document-model-list"],
      navigation: () => ["Model", "Document Models"],
      confirmClose: true,
      step: 1,
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Scan Completed",
        },
      ],
    },
    {
      id: "select-or-add-credentials",
      step: 2,
      component: StepComponents["select-or-add-credentials"],
      navigation: () => ["Model", "Document Models", "Credentials"],
      confirmClose: true,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Scan Completed",
        },
      ],
    },
    {
      id: "extracting-model-status",
      step: 3,
      confirmClose: false,
      navigation: () => ["Model", "Document Models", "Model Onboarding"],
      component: StepComponents["extracting-model"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Scan Completed",
        },
      ],
    },
    {
      id: "scan-completed",
      step: 4,
      confirmClose: true,
      navigation: () => ["Model", "Document Models", "Success"],
      component: StepComponents["scan-completed"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model Onboarding",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Scan Completed",
        },
      ],
    },
  ],
};

const securityScan: DrawerFlowType = {
  title: "Security Scan",
  description: "Run a security scan on the model",
  totalSteps: 2,
  steps: [
    {
      id: "security-scan-status",
      navigation: () => [
        "Model",
        `${useModels.getState().selectedModel?.name || useDeployModel.getState().currentWorkflow.workflow_steps.model.name}`,
        "Security Scan",
      ],
      confirmClose: true,
      step: 1,
      component: StepComponents["security-scan-status"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Security Scan",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Scan Completed",
        },
      ],
    },
    {
      id: "model-scan-completed",
      step: 2,
      confirmClose: true,
      navigation: () => [
        "Model",
        `${useModels.getState().selectedModel?.name}`,
        "Security Scan",
      ],
      component: StepComponents["scan-completed"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Security Scan",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Scan Completed",
        },
      ],
    },
  ],
};

const runModelEvaluations: DrawerFlowType = {
  title: "Run Model Evaluations",
  description: "Run evaluations on the model",
  totalSteps: 7,
  steps: [
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "select-model-evaluations",
      step: 1,
      confirmClose: false,
      component: StepComponents["select-model-evaluations"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "select-cluster-evaluations",
      confirmClose: true,
      step: 2,
      component: StepComponents["select-cluster-evaluations"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "select-credentials",
      step: 3,
      confirmClose: true,
      component: StepComponents["select-credentials"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "evaluation-information",
      confirmClose: true,
      step: 4,
      component: StepComponents["evaluation-information"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "evaluation-results",
      confirmClose: true,
      step: 5,
      component: StepComponents["evaluation-results"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "run-model-success",
      confirmClose: false,
      step: 6,
      component: StepComponents["run-model-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Stop Warning",
        },
      ],
    },
    {
      navigation: () => ["Projects", "Run Model Evaluations"],
      id: "stop-warning",
      confirmClose: true,
      step: 7,
      component: StepComponents["stop-warning"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Model Evaluations",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Information",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Results",
        },
        {
          status: FormProgressStatus.completed,
          title: "Success",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Stop Warning",
        },
      ],
    },
  ],
};

const editModel: DrawerFlowType = {
  title: "Edit Model",
  description: "Edit an existing model",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Projects", "Edit Model"],
      confirmClose: false,
      id: "edit-model",
      step: 1,
      component: StepComponents["edit-model"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Edit Model",
        },
      ],
    },
  ],
};

// Cluster Type Selector
const clusterTypeSelector: DrawerFlowType = {
  title: "Cluster Type Selector",
  description: "Select the type of cluster to add",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Cluster", "Select Cluster Type"],
      confirmClose: false,
      id: "add-cluster-select-source",
      step: 1,
      component: StepComponents["add-cluster-select-source"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Cluster Type",
        },
      ],
    },
  ],
};

// Cluster Provider Selector ConfigureClusterDetails
const clusterProviderSelector: DrawerFlowType = {
  title: "Cluster Provider Selector",
  description: "Select the provider of the cluster to add",
  totalSteps: 3,
  steps: [
    {
      navigation: () => ["Cluster", "Select Cluster Provider"],
      confirmClose: false,
      id: "add-cluster-select-provider",
      step: 1,
      component: StepComponents["add-cluster-select-provider"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Cluster Provider",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Choose Cloud Credential",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure Cluster Details",
        },
      ],
    },
    {
      navigation: () => ["Cluster", "Choose Cloud Credential"],
      confirmClose: false,
      id: "choose-cloud-credential",
      step: 2,
      component: StepComponents["choose-cloud-credential"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Choose Cloud Credential",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Choose Cloud Credential",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure Cluster Details",
        },
      ],
    },
    {
      navigation: () => ["Cluster", "Choose Cloud Credential"],
      confirmClose: false,
      id: "configure-cluster-details",
      step: 3,
      component: StepComponents["configure-cluster-details"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Choose Cloud Credential",
        },
        {
          status: FormProgressStatus.completed,
          title: "Choose Cloud Credential",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configure Cluster Details",
        },
      ],
    },
  ],
};

const addCluster: DrawerFlowType = {
  title: "Add Cluster",
  description: "Add a new cluster",
  totalSteps: 3,
  steps: [
    {
      navigation: () => ["Cluster", "Add Cluster"],
      confirmClose: false,
      id: "add-cluster",
      step: 1,
      component: StepComponents["add-cluster"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Add Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Cluster Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => ["Cluster", "Add Cluster"],
      confirmClose: true,
      id: "create-cluster-status",
      step: 2,
      component: StepComponents["create-cluster-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Add Cluster",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Cluster Onboarding",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => ["Cluster", "Add Cluster"],
      confirmClose: false,
      id: "create-cluster-success",
      step: 3,
      component: StepComponents["create-cluster-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Add Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cluster Onboarding",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
    },
  ],
};

const editCluster: DrawerFlowType = {
  title: "Edit Cluster",
  description: "Edit an existing cluster",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Clusters", "Edit Cluster"],
      confirmClose: false,
      id: "edit-cluster",
      step: 1,
      component: StepComponents["edit-cluster"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Edit Cluster",
        },
      ],
    },
  ],
};

const viewModel: DrawerFlowType = {
  title: "View Model",
  description: "View model details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Model",
        `${useModels.getState().selectedModel?.name}`,
      ],
      id: "view-model-details",
      confirmClose: false,
      step: 1,
      component: StepComponents["view-model-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "View Model",
        },
      ],
    },
    {
      id: "model-scan-result",
      step: 2,
      confirmClose: false,
      navigation: () => [
        "Model",
        `${useModels.getState().selectedModel?.name}`,
        "Security Scan",
      ],
      component: StepComponents["scan-completed"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "View Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Scan Result",
        },
      ],
    },
  ],
};

const editProject: DrawerFlowType = {
  title: "Edit Project",
  description: "Edit an existing project",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Edit Project",
      ],
      id: "edit-project",
      confirmClose: false,
      step: 1,
      component: StepComponents["edit-project"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Edit Project",
        },
      ],
    },
  ],
};

const addMembers: DrawerFlowType = {
  title: "Add Members",
  description: "Add members to the project",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Project",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        "Add Members",
      ],
      id: "add-members",
      confirmClose: false,
      step: 1,
      component: StepComponents["add-members"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Add Members",
        },
      ],
    },
  ],
};

const addWorker: DrawerFlowType = {
  title: "Add Worker",
  description: "Add a new worker",
  totalSteps: 5,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Worker",
      ],
      id: "add-worker",
      confirmClose: false,
      step: 1,
      component: StepComponents["add-worker"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Add Worker",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Cluster Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,

        "Add Worker",
      ],
      id: "add-worker-cluster-config-status",
      confirmClose: false,
      step: 2,
      component: StepComponents["add-worker-cluster-config-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Cluster Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,

        "Add Worker",
      ],
      id: "add-worker-cluster-config",
      confirmClose: false,
      step: 3,
      component: StepComponents["add-worker-cluster-configuration"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Add Worker",
        },
        {
          status: FormProgressStatus.completed,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Cluster Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },

    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,

        "Add Worker",
      ],
      id: "add-worker-deploy-status",
      confirmClose: false,
      step: 2,
      component: StepComponents["add-worker-deploy-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.completed,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cluster Configuration",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Worker",
      ],
      id: "add-worker-success",
      confirmClose: false,
      step: 5,
      component: StepComponents["add-worker-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Add Worker",
        },
        {
          status: FormProgressStatus.completed,
          title: "Checking Cluster Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Cluster Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Onboarding Worker",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
    },
  ],
};

const workerDetails: DrawerFlowType = {
  title: "Worker Details",
  description: "View worker details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useWorkers.getState().selectedWorker?.name}`,
      ],
      id: "worker-details",
      confirmClose: false,
      step: 1,
      component: StepComponents["worker-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Worker Details",
        },
      ],
    },
  ],
};

const useModel: DrawerFlowType = {
  title: "Use Model",
  description: "Use a model in a project",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Projects", "Use Model"],
      id: "use-model",
      confirmClose: false,
      step: 1,
      component: StepComponents["use-model"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Use Model",
        },
      ],
    },
  ],
};

const useAgent: DrawerFlowType = {
  title: "Use Agent",
  description: "Use an agent/prompt",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Agents", "Use Agent"],
      id: "use-agent",
      confirmClose: false,
      step: 1,
      component: StepComponents["use-agent"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Use Agent",
        },
      ],
    },
  ],
};

const useGuardrail: DrawerFlowType = {
  title: "Use Guardrail",
  description: "Use a guardrail in your application",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Guardrails", "Use Guardrail"],
      id: "use-guardrail",
      confirmClose: false,
      step: 1,
      component: StepComponents["use-guardrail"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Use Guardrail",
        },
      ],
    },
  ],
};

const publish: DrawerFlowType = {
  title: "Publish",
  description: "Publish deployment",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Projects", "Publish"],
      id: "publish",
      confirmClose: false,
      step: 1,
      component: StepComponents["publish"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "publish",
        },
      ],
    },
  ],
};

const publishEndpoint: DrawerFlowType = {
  title: "Publish Endpoint",
  description: "Publish endpoint with pricing",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Projects", "Publish Endpoint"],
      id: "publish-endpoint",
      confirmClose: false,
      step: 1,
      component: StepComponents["publish-endpoint"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Add Token Pricing",
        },
      ],
    },
  ],
};

const deleteCluster: DrawerFlowType = {
  title: "Delete Cluster",
  description: "Delete a cluster",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Clusters", "Delete Cluster"],
      id: "delete-cluster",
      confirmClose: false,
      step: 1,
      component: StepComponents["delete-cluster"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Cluster",
        },
      ],
    },
  ],
};

const deleteProject: DrawerFlowType = {
  title: "Delete Project",
  description: "Delete a project",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Project", "Delete Project"],
      confirmClose: false,
      id: "delete-project",
      step: 1,
      component: StepComponents["delete-project"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Project",
        },
      ],
    },
  ],
};

const deletingEndpoint: DrawerFlowType = {
  title: "Deleting Deployment",
  description: "Deleting Deployment",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Deployment", "Delete Deployment"],
      id: "delete-endpoint-status",
      confirmClose: false,
      step: 1,
      component: StepComponents["delete-endpoint-status"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Endpoint",
        },
      ],
    },
  ],
};

const deletingCluster: DrawerFlowType = {
  title: "Deleting Cluster",
  description: "Deleting Cluster",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Cluster", "Delete Cluster"],
      id: "delete-cluster-status",
      confirmClose: false,
      step: 1,
      component: StepComponents["delete-cluster-status"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Cluster",
        },
      ],
    },
  ],
};

const deletingWorker: DrawerFlowType = {
  title: "Deleting Worker",
  description: "Deleting Worker",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Deployment", "Delete Worker"],
      id: "delete-worker-status",
      confirmClose: false,
      step: 1,
      component: StepComponents["delete-worker-status"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Worker",
        },
      ],
    },
  ],
};

const addCredentials: DrawerFlowType = {
  title: "Add Credentials",
  description: "Add credentials for a provider",
  totalSteps: 3,
  steps: [
    {
      navigation: () => ["Credentials", "Add Credentials"],
      id: "add-credentials-choose-provider",
      step: 1,
      component: StepComponents["add-credentials-choose-provider"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Enter Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Credentials", "Add Credentials"],
      id: "add-credentials-form",
      step: 2,
      component: StepComponents["add-credentials-form"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Enter Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Credentials", "Add Credentials"],
      id: "credentials-success",
      properties: {
        text: "Credentials added Successfully",
      },
      step: 3,
      component: StepComponents["credentials-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.completed,
          title: "Enter Credentials",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};
const viewCredentials: DrawerFlowType = {
  title: "Credentials",
  description: "View credentials for a provider",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Credentials", "Credentials"],
      id: "view-credentials",
      step: 1,
      component: StepComponents["view-credentials"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Provider",
        },
      ],
      confirmClose: false,
    },
  ],
};

const viewProjectCredentials: DrawerFlowType = {
  title: "Credentials",
  description: "View credentials for a project",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Credentials", "API"],
      id: "view-project-credentials",
      step: 1,
      component: StepComponents["view-project-credentials"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Credential Name",
        },
      ],
      confirmClose: false,
    },
  ],
};

const addNewKey: DrawerFlowType = {
  title: "New Key",
  description: "Create new key",
  totalSteps: 2,
  steps: [
    {
      navigation: () => ["Credentials", "New Key"],
      id: "add-new-key",
      step: 1,
      component: StepComponents["add-new-key"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Key",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Credentials", "Add Credentials"],
      id: "credentials-success",
      properties: {
        text: "Credentials added Successfully",
      },
      step: 3,
      component: StepComponents["credentials-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Key",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const editprojectCredential: DrawerFlowType = {
  title: "Update Credentials",
  description: "Update project credentials",
  totalSteps: 2,
  steps: [
    {
      navigation: () => ["Credentials", "Update Credentials"],
      id: "ed",
      step: 1,
      component: StepComponents["edit-project-credential"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Key",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Credentials", "Update Credentials"],
      id: "credentials-Update-success",
      properties: {
        text: "Credentials updated Successfully",
      },
      step: 3,
      component: StepComponents["credentials-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Key",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const licenseDetails: DrawerFlowType = {
  title: "License Details",
  description: "License Details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["License", "Details"],
      id: "license-Details",
      confirmClose: false,
      step: 1,
      component: StepComponents["license-Details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "View licence details",
        },
      ],
    },
  ],
};

const derivedModelList: DrawerFlowType = {
  title: "Derived Models",
  description: "View derived models",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Model", "Derived Models"],
      id: "derived-model-list",
      confirmClose: false,
      step: 1,
      component: StepComponents["derived-model-list"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "View licence details",
        },
      ],
    },
  ],
};

const clusterEvent: DrawerFlowType = {
  title: "Event",
  description: "Info Description",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Cluster", "Event"],
      id: "cluster-event",
      confirmClose: false,
      step: 1,
      component: StepComponents["cluster-event"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Event",
        },
      ],
    },
  ],
};

const viewUser: DrawerFlowType = {
  title: "User Management",
  description: "User Management",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["User Management", "View User"],
      id: "view-user",
      confirmClose: false,
      step: 1,
      component: StepComponents["view-user"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Event",
        },
      ],
    },
  ],
};
const editUser: DrawerFlowType = {
  title: "User Management",
  description: "User Management",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["User Management", "Edit User"],
      id: "edit-user",
      confirmClose: false,
      step: 1,
      component: StepComponents["edit-user"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Event",
        },
      ],
    },
  ],
};

const resetPassword: DrawerFlowType = {
  title: "User Management",
  description: "User Management",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["User Management", "Reset Password"],
      id: "reset-password",
      confirmClose: false,
      step: 1,
      component: StepComponents["reset-password"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Event",
        },
      ],
    },
  ],
};

const addUser: DrawerFlowType = {
  title: "User Management",
  description: "User Management",
  totalSteps: 2,
  steps: [
    {
      navigation: () => ["User Management", "Add User"],
      id: "add-user",
      confirmClose: false,
      step: 1,
      component: StepComponents["add-user"],
      progress: [],
    },
    {
      navigation: () => ["User Management", "Invite User"],
      id: "add-user-details",
      confirmClose: false,
      step: 1,
      component: StepComponents["add-user-details"],
      progress: [],
    },
  ],
};

const userUsage: DrawerFlowType = {
  title: "Usage Values",
  description: "Description for usage values...",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["User Management", "Usage Values"],
      id: "user-usage",
      confirmClose: false,
      step: 1,
      component: StepComponents["user-usage"],
      progress: [],
    },
  ],
};

const logDetails: DrawerFlowType = {
  title: "Log Details",
  description: "View span details and raw data",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Logs", "Details"],
      id: "log-details",
      confirmClose: false,
      step: 1,
      component: StepComponents["log-details"],
      progress: [],
    },
  ],
};

const addBenchmark: DrawerFlowType = {
  title: "Add Benchmark",
  description: "Add Benchmark",
  totalSteps: 9,
  steps: [
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "model_benchmark",
      confirmClose: false,
      step: 1,
      component: StepComponents["model_benchmark"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "add-Datasets",
      confirmClose: true,
      step: 2,
      component: StepComponents["Datasets"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "add-Configuration",
      confirmClose: true,
      step: 2,
      component: StepComponents["Configuration"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Select-Cluster",
      confirmClose: true,
      step: 3,
      component: StepComponents["Select-Cluster"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Select-Hardware-Mode",
      confirmClose: true,
      step: 4,
      component: StepComponents["Select-Hardware-Mode"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Select-Nodes",
      confirmClose: true,
      step: 5,
      component: StepComponents["Select-Nodes"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Select-Model",
      confirmClose: true,
      step: 6,
      component: StepComponents["Select-Model"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "model_benchmark-credential-select",
      confirmClose: true,
      step: 6,
      component: StepComponents["model_benchmark-credential-select"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Credentials",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Select-Configuration",
      confirmClose: true,
      step: 7,
      component: StepComponents["Select-Configuration"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Benchmarking-Progress",
      confirmClose: true,
      step: 8,
      component: StepComponents["Benchmarking-Progress"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ],
    },
    {
      navigation: () => ["Benchmarks", "Create Benchmark"],
      id: "Benchmarking-Finished",
      confirmClose: false,
      step: 9,
      component: StepComponents["Benchmarking-Finished"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create benchmark",
        },
        {
          status: FormProgressStatus.completed,
          title: "Eval with",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Mode",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Nodes",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Configuration Options",
        },
        {
          status: FormProgressStatus.completed,
          title: "Running Benchmark",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Result",
        },
      ],
    },
  ],
};
const addQuantizationFlow: DrawerFlowType = {
  title: "Add Quantization",
  description: "Add a new quantization",
  totalSteps: 7,
  steps: [
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-detail",
      confirmClose: false,
      component: StepComponents["quantization-detail"],
      step: 1,
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Method",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-method",
      confirmClose: true,
      component: StepComponents["quantization-method"],
      step: 2,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Method",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result"
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "advanced-settings",
      confirmClose: true,
      component: StepComponents["advanced-settings"],
      step: 3,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.completed,
          title: "Method",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result"
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-simulation-status",
      confirmClose: true,
      component: StepComponents["quantization-simulation-status"],
      step: 4,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.completed,
          title: "Method",
        },
        {
          status: FormProgressStatus.completed,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result"
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-select-cluster",
      confirmClose: true,
      component: StepComponents["quantization-select-cluster"],
      step: 5,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.completed,
          title: "Method",
        },
        {
          status: FormProgressStatus.completed,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.completed,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result"
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-deployment-status",
      confirmClose: true,
      component: StepComponents["quantization-deployment-status"],
      step: 6,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.completed,
          title: "Method",
        },
        {
          status: FormProgressStatus.completed,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.completed,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Result",
        },
      ]
    },
    {
      navigation: () => ["Model", "Add Quantization"],
      id: "quantization-result",
      confirmClose: true,
      component: StepComponents["quantization-result"],
      step: 7,
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Quantization Details",
        },
        {
          status: FormProgressStatus.completed,
          title: "Method",
        },
        {
          status: FormProgressStatus.completed,
          title: "Advanced",
        },
        {
          status: FormProgressStatus.completed,
          title: "Simulation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select cluster",
        },
        {
          status: FormProgressStatus.completed,
          title: "Running quantization",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Result"
        },
      ]
    }
  ]
}

const runNewSumulation: DrawerFlowType = {
  title: "Simulations & Evaluations",
  description: "Run new Simulations",
  totalSteps: 7,
  steps: [
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "select-evaluation-type",
      step: 1,
      component: StepComponents["select-evaluation-type"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "select-use-case",
      step: 2,
      component: StepComponents["select-use-case"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "additional-settingse",
      step: 3,
      component: StepComponents["additional-settings"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "select-model-for-evaluation",
      step: 4,
      component: StepComponents["select-model-for-evaluation"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.completed,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "model-quantisation",
      step: 5,
      component: StepComponents["model-quantisation"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.completed,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "select-hardware",
      step: 5,
      component: StepComponents["select-hardware"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.completed,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "hardware-pecifications",
      step: 5,
      component: StepComponents["hardware-pecifications"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.completed,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Simulations & Evaluations"],
      id: "simulation-details",
      step: 5,
      component: StepComponents["simulation-details"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Use Case",
        },
        {
          status: FormProgressStatus.completed,
          title: "Additional Settings",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Model Quantisation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Hardware",
        },
        {
          status: FormProgressStatus.completed,
          title: "Hardware Secifications",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Simulation Details",
        },
      ],
      confirmClose: false,
    },
  ],
};

const addAdapter: DrawerFlowType = {
  title: "Add Adapter",
  description: "Add a new adapter",
  totalSteps: 4,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Adapter",
      ],
      id: "add-adapter-select-model",
      confirmClose: false,
      step: 1,
      component: StepComponents["add-adapter-select-model"],
      progress: [
        {
          "status": FormProgressStatus.inProgress,
          "title": "Select Model",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Adapter details",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Deployment status",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Deployment result",
        }
      ]
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Adapter",
      ],
      id: "add-adapter-detail",
      confirmClose: false,
      step: 2,
      component: StepComponents["add-adapter-detail"],
      progress: [
        {
          "status": FormProgressStatus.completed,
          "title": "Select Model",
        },
        {
          "status": FormProgressStatus.inProgress,
          "title": "Adapter details",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Deployment status",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Deployment result",
        }
      ]
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Adapter",
      ],
      id: "add-adapter-status",
      confirmClose: false,
      step: 3,
      component: StepComponents["add-adapter-status"],
      progress: [
        {
          "status": FormProgressStatus.completed,
          "title": "Select Model",
        },
        {
          "status": FormProgressStatus.completed,
          "title": "Adapter details",
        },
        {
          "status": FormProgressStatus.inProgress,
          "title": "Deployment status",
        },
        {
          "status": FormProgressStatus.notCompleted,
          "title": "Deployment result",
        }
      ]
    },
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Add Adapter",
      ],
      id: "add-adapter-result",
      confirmClose: false,
      step: 4,
      component: StepComponents["add-adapter-result"],
      progress: [
        {
          "status": FormProgressStatus.completed,
          "title": "Select Model",
        },
        {
          "status": FormProgressStatus.completed,
          "title": "Adapter details",
        },
        {
          "status": FormProgressStatus.completed,
          "title": "Deployment status",
        },
        {
          "status": FormProgressStatus.inProgress,
          "title": "Deployment result",
        }
      ]
    }
  ]
}
const deleteAdapter: DrawerFlowType = {
  title: "Deleting Adapter",
  description: "Deleting Adapter",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Projects",
        `${useProjects.getState().selectedProject?.icon} ${useProjects.getState().selectedProject?.name}`,
        `${useDeployModel.getState().currentWorkflow?.workflow_steps?.endpoint?.name || useEndPoints.getState().clusterDetails?.name}`,
        "Delete Adapter",
      ],
      id: "delete-adapter-status",
      confirmClose: false,
      step: 1,
      component: StepComponents["delete-adapter-status"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Delete Adapter",
        },
      ],
    },
  ],
};

const editProfile: DrawerFlowType = {
  title: "Edit Profile",
  description: "Edit Profile",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Edit Profile",
      ],
      id: "edit-user-profile",
      confirmClose: false,
      step: 1,
      component: StepComponents["edit-user-profile"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Edit Profile",
        },
      ],
    },
  ],
};

const createRoute: DrawerFlowType = {
  title: "Create Route",
  description: "Create Route",
  totalSteps: 2,
  steps: [
    {
      navigation: () => [
        "Create Route",
      ],
      id: "create-route-data",
      confirmClose: false,
      step: 1,
      component: StepComponents["create-route-data"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Create Route",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "select Endpoints",
        },
      ],
    },
    {
      navigation: () => [
        "Create Route",
      ],
      id: "select-endpoints-route",
      confirmClose: false,
      step: 2,
      component: StepComponents["select-endpoints-route"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Create Route",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "select Endpoints",
        },
      ],
    },
  ],
};


// Flow for selecting fallback deployment
const selectFallbackDeployment: DrawerFlowType = {
  title: "Select Fallback Deployment",
  description: "Choose a fallback deployment",
  totalSteps: 1,
  steps: [
    {
      navigation: () => [
        "Select Fallback Deployment",
      ],
      id: "select-fallback-deployment",
      confirmClose: false,
      step: 1,
      component: StepComponents["select-fallback-deployment"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Deployment",
        },
      ],
    },
  ],
};

// New Experiment Flow
const newExperiment: DrawerFlowType = {
  title: "New Experiment",
  description: "Create a new experiment",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Experiments", "New Experiment"],
      id: "new-experiment",
      step: 1,
      component: StepComponents["new-experiment"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Experiment",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Experiments", "New Experiment"],
      id: "new-experiment-success",
      step: 1,
      component: StepComponents["new-experiment-success"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Experiment",
        },
      ],
      confirmClose: false,
    },
  ],
};



const runEvaluation: DrawerFlowType = {
  title: "New Evaluation",
  description: "New Evaluation",
  totalSteps: 7,
  steps: [
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "new-evaluation",
      confirmClose: true,
      step: 1,
      component: StepComponents["new-evaluation"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "select-model-new-evaluation",
      confirmClose: true,
      step: 2,
      component: StepComponents["select-model-new-evaluation"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "select-traits",
      confirmClose: true,
      step: 3,
      component: StepComponents["select-traits"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "select-evaluation",
      confirmClose: true,
      step: 4,
      component: StepComponents["select-evaluation"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "evaluation-summary",
      confirmClose: true,
      step: 5,
      component: StepComponents["evaluation-summary"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "run-evaluation-status",
      confirmClose: true,
      step: 6,
      component: StepComponents["run-evaluation-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Evaluation Complete",
        },
      ],
    },
    {
      navigation: () => [
        "New Evaluation",
      ],
      id: "run-evaluation-success",
      confirmClose: false,
      step: 7,
      component: StepComponents["run-evaluation-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "New Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Traits",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Summary",
        },
        {
          status: FormProgressStatus.completed,
          title: "Running Evaluation",
        },
        {
          status: FormProgressStatus.completed,
          title: "Evaluation Complete",
        },
      ],
    },

  ],
};

const viewEvalDetails: DrawerFlowType = {
  title: "Evaluation Details",
  description: "View Evaluation Details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Experiments", "Evaluation Details"],
      id: "eval-details",
      step: 1,
      component: StepComponents["view-eval-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "New evaluation",
        },
      ],
      confirmClose: false,
    },
  ],
};

const createBlockingRule: DrawerFlowType = {
  title: "Create Blocking Rule",
  description: "Create a new blocking rule for the gateway",
  totalSteps: 2,
  steps: [
    {
      navigation: () => ["Blocking Rules", "Create Rule"],
      id: "create-blocking-rule",
      step: 1,
      component: StepComponents["create-blocking-rule"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Rule Details",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Blocking Rules", "Success"],
      id: "blocking-rule-success",
      step: 2,
      component: StepComponents["blocking-rule-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Rule Details",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const viewBlockingRule: DrawerFlowType = {
  title: "Blocking Rule Details",
  description: "View blocking rule details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Blocking Rules", "Rule Details"],
      id: "view-blocking-rule",
      step: 1,
      component: StepComponents["view-blocking-rule"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Rule Details",
        },
      ],
      confirmClose: false,
    },
  ],
};

const viewProbeDetails: DrawerFlowType = {
  title: "Probe Details",
  description: "View Probe Details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Guardrails", "Probe Details"],
      id: "probe-details",
      step: 1,
      component: StepComponents["probe-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Probe Details",
        },
      ],
      confirmClose: false,
    },
  ],
};

const viewGuardrailDetails: DrawerFlowType = {
  title: "Guardrail Details",
  description: "View guardrail details and deploy",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Guardrails", "Guardrail Details"],
      id: "view-guardrail-details",
      step: 1,
      component: StepComponents["view-guardrail-details"],
      progress: [],
      confirmClose: false,
    },
  ],
};

const addGuardrail: DrawerFlowType = {
  title: "Add Guardrail",
  description: "Configure guardrails for your models",
  totalSteps: 15,
  steps: [
    {
      navigation: () => ["Guardrails", "Select Provider"],
      id: "select-provider",
      step: 1,
      component: StepComponents["select-provider"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Probes List"],
      id: "bud-sentinel-probes",
      step: 2,
      component: StepComponents["bud-sentinel-probes"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Probes",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "PII Detection"],
      id: "pii-detection-config",
      step: 3,
      component: StepComponents["pii-detection-config"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Probes",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configure PII",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Deployment Types"],
      id: "deployment-types",
      step: 4,
      component: StepComponents["deployment-types"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Configure PII",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Deployment Type",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Select Project"],
      id: "select-project",
      step: 5,
      component: StepComponents["select-project"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deployment Type",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Select Deployment"],
      id: "select-deployment",
      step: 6,
      component: StepComponents["select-deployment"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Deployment",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Probe Settings"],
      id: "probe-settings",
      step: 7,
      component: StepComponents["probe-settings"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Deployment",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Probe Settings",
        },
      ],
      confirmClose: true,
    },
    // {
    //   navigation: () => ["Guardrails", "Deploying"],
    //   id: "deploying-probe",
    //   step: 8,
    //   component: StepComponents["deploying-probe"],
    //   progress: [
    //     {
    //       status: FormProgressStatus.completed,
    //       title: "Probe Settings",
    //     },
    //     {
    //       status: FormProgressStatus.inProgress,
    //       title: "Deploying",
    //     },
    //   ],
    //   confirmClose: false,
    // },
    {
      navigation: () => ["Guardrails", "Success"],
      id: "probe-deployment-success",
      step: 9,
      component: StepComponents["probe-deployment-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Deploying",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Guardrails", "Configure"],
      id: "politeness-detection",
      step: 10,
      component: StepComponents["politeness-detection"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Select Probe Type"],
      id: "select-probe-type",
      step: 11,
      component: StepComponents["select-probe-type"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Provider",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Custom GuardRail"],
      id: "add-custom-guardrail",
      step: 12,
      component: StepComponents["add-custom-guardrail"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configure Rules",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Upload Dataset"],
      id: "upload-dataset",
      step: 13,
      component: StepComponents["upload-dataset"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Upload Dataset",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Train",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Guardrails", "Training"],
      id: "training-probe",
      step: 14,
      component: StepComponents["training-probe"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Upload Dataset",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Train",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Details",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Guardrails", "Details"],
      id: "guardrail-details",
      step: 15,
      component: StepComponents["guardrail-details"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Configure",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Details",
        },
      ],
      confirmClose: true,
    },
  ],
};

// Flow For Adding Agent
const addAgent: DrawerFlowType = {
  title: "Add Agent",
  description: "Create a new agent",
  totalSteps: 6,
  steps: [
    {
      navigation: () => ["Select Project", "Add Agent"],
      id: "add-agent-select-project",
      step: 1,
      component: StepComponents["add-agent-select-project"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Review",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Select Type", "Add Agent"],
      id: "add-agent-select-type",
      step: 2,
      component: StepComponents["add-agent-select-type"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Review",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Select Model", "Add Agent"],
      id: "add-agent-select-model",
      step: 3,
      component: StepComponents["add-agent-select-model"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Review",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Configuration", "Add Agent"],
      id: "add-agent-configuration",
      step: 4,
      component: StepComponents["add-agent-configuration"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Review",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Review", "Add Agent"],
      id: "add-agent-deployment-warning",
      step: 5,
      component: StepComponents["add-agent-deployment-warning"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Review",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
    {
      navigation: () => ["Success", "Add Agent"],
      id: "add-agent-success",
      step: 6,
      component: StepComponents["add-agent-success"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Project",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Type",
        },
        {
          status: FormProgressStatus.completed,
          title: "Select Model",
        },
        {
          status: FormProgressStatus.completed,
          title: "Configuration",
        },
        {
          status: FormProgressStatus.completed,
          title: "Review",
        },
        {
          status: FormProgressStatus.completed,
          title: "Success",
        },
      ],
      confirmClose: false,
    },
  ],
};

const editAgent: DrawerFlowType = {
  title: "Edit Agent",
  description: "Edit agent details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Agents", "Edit Agent"],
      id: "edit-agent-drawer",
      step: 1,
      component: StepComponents["edit-agent-drawer"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Edit Agent",
        },
      ],
      confirmClose: false,
    },
  ],
};

// Flow For New Workflow
const newPipeline: DrawerFlowType = {
  title: "New Workflow",
  description: "Create a new DAG workflow",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Workflows", "New Workflow"],
      id: "new-pipeline",
      step: 1,
      component: StepComponents["new-pipeline"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Create Workflow",
        },
      ],
      confirmClose: false,
    },
  ],
};

const viewTool: DrawerFlowType = {
  title: "View Tool",
  description: "View tool details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Tools", "View Tool"],
      id: "view-tool-details",
      step: 1,
      component: StepComponents["view-tool-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "View Tool",
        },
      ],
      confirmClose: false,
    },
  ],
};

const pipelineExecutionDetails: DrawerFlowType = {
  title: "Execution Details",
  description: "View workflow execution details",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Workflows", "Execution Details"],
      id: "pipeline-execution-details",
      step: 1,
      component: StepComponents["pipeline-execution-details"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Execution Details",
        },
      ],
      confirmClose: false,
    },
  ],
};

const addTool: DrawerFlowType = {
  title: "Add Tool",
  description: "Add a new tool",
  totalSteps: 3,
  steps: [
    {
      navigation: () => ["Tools", "Add Tool"],
      id: "select-tool-source",
      step: 1,
      component: StepComponents["select-tool-source"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.notCompleted,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Tools", "Add Tool", "Bud Catalogue"],
      id: "bud-tools-catalogue",
      step: 2,
      component: StepComponents["bud-tools-catalogue"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Select Tools",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Tools", "Add Tool", "OpenAPI Specification"],
      id: "openapi-specification",
      step: 2,
      component: StepComponents["openapi-specification"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Configure",
        },
      ],
      confirmClose: true,
    },
    {
      navigation: () => ["Tools", "Add Tool", "Creating Tool"],
      id: "creating-tool-status",
      step: 3,
      component: StepComponents["creating-tool-status"],
      progress: [
        {
          status: FormProgressStatus.completed,
          title: "Select Source",
        },
        {
          status: FormProgressStatus.completed,
          title: "Configure",
        },
        {
          status: FormProgressStatus.inProgress,
          title: "Creating",
        },
      ],
      confirmClose: false,
    },
  ],
};

const pipelineCreateSchedule: DrawerFlowType = {
  title: "Create Schedule",
  description: "Create a workflow schedule",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Workflows", "Create Schedule"],
      id: "pipeline-create-schedule",
      step: 1,
      component: StepComponents["pipeline-create-schedule"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Create Schedule",
        },
      ],
      confirmClose: false,
    },
  ],
};

const toolDetailsExpanded: DrawerFlowType = {
  title: "Tool Details",
  description: "View tool details and sub-tools",
  totalSteps: 1,
  steps: [
    {
      navigation: () => ["Tools", "Tool Details"],
      id: "tool-details-expanded",
      step: 1,
      component: StepComponents["tool-details-expanded"],
      progress: [
        {
          status: FormProgressStatus.inProgress,
          title: "Tool Details",
        },
      ],
      confirmClose: false,
    },
  ],
};

const flows = {
  "new-project": newProject,
  "deploy-model": deployModel,
  "add-model": addModel,
  "add-model-cloud-flow": addModelCloudFlow,
  "add-model-local-flow": addModelLocalFlow,
  "document-model-flow": documentModelFlow,
  "security-scan": securityScan,
  "run-model-evaluations": runModelEvaluations,
  "edit-model": editModel,
  "add-cluster": addCluster,
  "edit-cluster": editCluster,
  "view-model": viewModel,
  "edit-project": editProject,
  "add-members": addMembers,
  "add-worker": addWorker,
  "worker-details": workerDetails,
  "use-model": useModel,
  "use-agent": useAgent,
  "publish": publish,
  "publish-endpoint": publishEndpoint,
  "delete-cluster": deleteCluster,
  "delete-project": deleteProject,
  "deleting-endpoint": deletingEndpoint,
  "deleting-cluster": deletingCluster,
  "add-credentials": addCredentials,
  "view-credentials": viewCredentials,
  "view-project-credentials": viewProjectCredentials,
  "add-new-key": addNewKey,
  "edit-project-credential": editprojectCredential,
  "license-Details": licenseDetails,
  "derived-model-list": derivedModelList,
  "cluster-event": clusterEvent,
  "deleting-worker": deletingWorker,
  "view-user": viewUser,
  "edit-user": editUser,
  "reset-password": resetPassword,
  "add-user": addUser,
  "user-usage": userUsage,
  "log-details": logDetails,
  "model_benchmark": addBenchmark,
  "add-quantization": addQuantizationFlow,
  "add-new-cloud-provider": addNewCloudProvider,

  // Cluster Specific
  "add-cluster-select-source": clusterTypeSelector,
  "add-cluster-select-provider": clusterProviderSelector,
  "run-new-sumulation": runNewSumulation,
  "add-adapter": addAdapter,
  "delete-adapter": deleteAdapter,
  // edit profile
  "edit-profile": editProfile,
  // route
  "create-route": createRoute,
  // deployment selection
  "select-fallback-deployment": selectFallbackDeployment,
  // experiments
  "new-experiment": newExperiment,
  "run-evaluation": runEvaluation,
  "eval-details": viewEvalDetails,
  // guardrails
  "add-guardrail": addGuardrail,
  "probe-details": viewProbeDetails,
  "view-guardrail-details": viewGuardrailDetails,
  "use-guardrail": useGuardrail,
  // blocking rules
  "create-blocking-rule": createBlockingRule,
  "view-blocking-rule": viewBlockingRule,
  // agent
  "add-agent": addAgent,
  "edit-agent": editAgent,
  // workflows
  "new-pipeline": newPipeline,
  "pipeline-execution-details": pipelineExecutionDetails,
  "pipeline-create-schedule": pipelineCreateSchedule,
  // tools
  "view-tool": viewTool,
  "add-tool": addTool,
  "tool-details-expanded": toolDetailsExpanded,
};

export const flowMapping: {
  [key: string]: Flow;
} = {
  'cloud_model_onboarding': 'add-model-cloud-flow',
  'local_model_onboarding': 'add-model-local-flow',
  'model_deployment': 'deploy-model',
  'cluster_onboarding': 'add-cluster',
  'model_security_scan': 'security-scan',
  'cluster_deletion': 'deleting-cluster',
  'endpoint_deletion': 'deleting-endpoint',
  'add_worker_to_endpoint': 'add-worker',
  'endpoint_worker_deletion': 'deleting-worker',
  'local_model_quantization': 'add-quantization',
  "add_adapter": "add-adapter",
  "delete_adapter": "delete-adapter",
  "model_benchmark": "model_benchmark",
  "evaluate_model": "run-evaluation",
  "prompt_creation": "add-agent",
}

export const inProgressSteps = [
  "deploy-cluster-status",
  "deploy-model-status",
  "extracting-model-status",
  "security-scan-status",
  "create-cluster-status",
  "delete-cluster-status",
  "delete-endpoint-status",
  "delete-worker-status",
  "deploy-quantization-status",
  "quantization-simulation-status",
  "quantization-deployment-status",
  "run-evaluation-status"
];

export type Flow = keyof typeof flows;

export default flows;
