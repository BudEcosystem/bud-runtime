/**
 * Zustand store for BudUseCases
 *
 * Manages state for:
 * - Templates browsing and selection
 * - Component selection
 * - Deployment creation wizard
 * - Deployment list and status monitoring
 */

import { create } from "zustand";
import {
  BudUseCasesAPI,
  Template,
  Deployment,
  DeploymentProgressResponse,
  CreateDeploymentRequest,
  CreateTemplateRequest,
  UpdateTemplateRequest,
} from "@/lib/budusecases";
import { errorToast, successToast } from "@/components/toast";
import { useProjects } from "src/hooks/useProjects";

// ============================================================================
// Types
// ============================================================================

export type DeploymentWizardStep =
  | "select-template"
  | "configure-components"
  | "set-parameters"
  | "select-cluster"
  | "review"
  | "deploying";

interface UseCasesState {
  // Templates
  templates: Template[];
  selectedTemplate: Template | null;
  templatesLoading: boolean;
  templatesTotal: number;
  templatesPage: number;

  // Component selections for deployment
  selectedComponents: Record<string, string>; // slot name -> component name

  // Deployment wizard
  wizardStep: DeploymentWizardStep;
  deploymentName: string;
  deploymentParameters: Record<string, any>;
  selectedClusterId: string | null;

  // Deployments
  deployments: Deployment[];
  selectedDeployment: Deployment | null;
  deploymentsLoading: boolean;
  deploymentsTotal: number;
  deploymentsPage: number;

  // Deployment progress polling
  deploymentProgress: DeploymentProgressResponse | null;
  progressPollingId: ReturnType<typeof setInterval> | null;

  // App overlay
  isAppOverlayOpen: boolean;

  // Error state
  error: string | null;
}

interface UseCasesActions {
  // Template actions
  fetchTemplates: (params?: { page?: number; category?: string; tag?: string; source?: string }) => Promise<void>;
  selectTemplate: (template: Template | null) => void;
  fetchTemplateByName: (name: string) => Promise<Template | null>;
  createTemplate: (request: CreateTemplateRequest) => Promise<Template | null>;
  updateTemplate: (templateId: string, request: UpdateTemplateRequest) => Promise<Template | null>;
  deleteTemplate: (templateId: string) => Promise<boolean>;

  // Component actions
  selectComponent: (slot: string, componentName: string) => void;
  clearComponentSelections: () => void;

  // Wizard actions
  setWizardStep: (step: DeploymentWizardStep) => void;
  setDeploymentName: (name: string) => void;
  setDeploymentParameter: (key: string, value: any) => void;
  setSelectedCluster: (clusterId: string | null) => void;
  resetWizard: () => void;

  // Deployment actions
  fetchDeployments: (params?: { page?: number; status?: string; cluster_id?: string; project_id?: string }) => Promise<void>;
  fetchDeployment: (deploymentId: string) => Promise<Deployment | null>;
  createDeployment: () => Promise<Deployment | null>;
  startDeployment: (deploymentId: string) => Promise<boolean>;
  stopDeployment: (deploymentId: string) => Promise<boolean>;
  deleteDeployment: (deploymentId: string) => Promise<boolean>;
  syncDeploymentStatus: (deploymentId: string) => Promise<void>;
  selectDeployment: (deployment: Deployment | null) => void;

  // Deployment progress polling
  pollDeploymentProgress: (deploymentId: string, intervalMs?: number) => void;
  stopPollingDeploymentProgress: () => void;

  // App overlay
  openAppOverlay: (deployment: Deployment) => void;
  closeAppOverlay: () => void;

  // Utility
  clearError: () => void;
}

type UseCasesStore = UseCasesState & UseCasesActions;

// ============================================================================
// Initial State
// ============================================================================

const initialState: UseCasesState = {
  // Templates
  templates: [],
  selectedTemplate: null,
  templatesLoading: false,
  templatesTotal: 0,
  templatesPage: 1,

  // Component selections
  selectedComponents: {},

  // Wizard
  wizardStep: "select-template",
  deploymentName: "",
  deploymentParameters: {},
  selectedClusterId: null,

  // Deployments
  deployments: [],
  selectedDeployment: null,
  deploymentsLoading: false,
  deploymentsTotal: 0,
  deploymentsPage: 1,

  // Deployment progress polling
  deploymentProgress: null,
  progressPollingId: null,

  // App overlay
  isAppOverlayOpen: false,

  // Error
  error: null,
};

// ============================================================================
// Store Implementation
// ============================================================================

export const useUseCases = create<UseCasesStore>((set, get) => ({
  ...initialState,

  // -------------------------------------------------------------------------
  // Template Actions
  // -------------------------------------------------------------------------

  fetchTemplates: async (params) => {
    set({ templatesLoading: true, error: null });
    try {
      const response = await BudUseCasesAPI.templates.list({
        page: params?.page || 1,
        page_size: 20,
        category: params?.category,
        tag: params?.tag,
        source: params?.source,
      });
      set({
        templates: response.items,
        templatesTotal: response.total,
        templatesPage: response.page,
        templatesLoading: false,
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to fetch templates";
      set({ error: message, templatesLoading: false });
      errorToast(message);
    }
  },

  selectTemplate: (template) => {
    set({
      selectedTemplate: template,
      selectedComponents: {},
      deploymentParameters: template?.parameters
        ? Object.fromEntries(
            Object.entries(template.parameters).map(([key, param]) => [key, param.default])
          )
        : {},
    });
  },

  fetchTemplateByName: async (name) => {
    try {
      const template = await BudUseCasesAPI.templates.getByName(name);
      set({ selectedTemplate: template });
      return template;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to fetch template";
      set({ error: message });
      errorToast(message);
      return null;
    }
  },

  createTemplate: async (request) => {
    try {
      const template = await BudUseCasesAPI.templates.create(request);
      successToast("Template created successfully");
      await get().fetchTemplates();
      return template;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to create template";
      errorToast(message);
      return null;
    }
  },

  updateTemplate: async (templateId, request) => {
    try {
      const template = await BudUseCasesAPI.templates.update(templateId, request);
      successToast("Template updated successfully");
      await get().fetchTemplates();
      return template;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to update template";
      errorToast(message);
      return null;
    }
  },

  deleteTemplate: async (templateId) => {
    try {
      await BudUseCasesAPI.templates.delete(templateId);
      successToast("Template deleted");
      set((state) => ({
        templates: state.templates.filter((t) => t.id !== templateId),
        selectedTemplate: state.selectedTemplate?.id === templateId ? null : state.selectedTemplate,
      }));
      return true;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to delete template";
      errorToast(message);
      return false;
    }
  },

  // -------------------------------------------------------------------------
  // Component Actions
  // -------------------------------------------------------------------------

  selectComponent: (slot, componentName) => {
    set((state) => ({
      selectedComponents: {
        ...state.selectedComponents,
        [slot]: componentName,
      },
    }));
  },

  clearComponentSelections: () => {
    set({ selectedComponents: {} });
  },

  // -------------------------------------------------------------------------
  // Wizard Actions
  // -------------------------------------------------------------------------

  setWizardStep: (step) => {
    set({ wizardStep: step });
  },

  setDeploymentName: (name) => {
    set({ deploymentName: name });
  },

  setDeploymentParameter: (key, value) => {
    set((state) => ({
      deploymentParameters: {
        ...state.deploymentParameters,
        [key]: value,
      },
    }));
  },

  setSelectedCluster: (clusterId) => {
    set({ selectedClusterId: clusterId });
  },

  resetWizard: () => {
    get().stopPollingDeploymentProgress();
    set({
      wizardStep: "select-template",
      selectedTemplate: null,
      selectedComponents: {},
      deploymentName: "",
      deploymentParameters: {},
      selectedClusterId: null,
      selectedDeployment: null,
      deploymentProgress: null,
      isAppOverlayOpen: false,
    });
  },

  // -------------------------------------------------------------------------
  // Deployment Actions
  // -------------------------------------------------------------------------

  fetchDeployments: async (params) => {
    set({ deploymentsLoading: true, error: null });
    try {
      const response = await BudUseCasesAPI.deployments.list({
        page: params?.page || 1,
        page_size: 20,
        status: params?.status,
        cluster_id: params?.cluster_id,
        project_id: params?.project_id,
      });
      set({
        deployments: response.items,
        deploymentsTotal: response.total,
        deploymentsPage: response.page,
        deploymentsLoading: false,
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to fetch deployments";
      set({ error: message, deploymentsLoading: false });
      errorToast(message);
    }
  },

  fetchDeployment: async (deploymentId) => {
    try {
      const deployment = await BudUseCasesAPI.deployments.get(deploymentId);
      set({ selectedDeployment: deployment });
      return deployment;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to fetch deployment";
      set({ error: message });
      errorToast(message);
      return null;
    }
  },

  createDeployment: async () => {
    const { selectedTemplate, selectedComponents, deploymentName, deploymentParameters, selectedClusterId } = get();

    if (!selectedTemplate || !selectedClusterId || !deploymentName) {
      errorToast("Missing required fields for deployment");
      return null;
    }

    set({ wizardStep: "deploying" });

    try {
      const projectId = useProjects.getState().selectedProject?.id || useProjects.getState().globalSelectedProject?.id;
      const request: CreateDeploymentRequest = {
        name: deploymentName,
        template_name: selectedTemplate.name,
        cluster_id: selectedClusterId,
        components: selectedComponents,
        parameters: deploymentParameters,
        ...(projectId ? { project_id: projectId } : {}),
      };

      const deployment = await BudUseCasesAPI.deployments.create(request);
      successToast("Deployment created successfully");

      // Start the deployment automatically
      const startResult = await BudUseCasesAPI.deployments.start(deployment.id);
      successToast("Deployment started");

      // Refresh deployment to get updated status
      const updatedDeployment = await BudUseCasesAPI.deployments.get(deployment.id);
      // Attach workflow_id from start response for CommonStatus real-time tracking
      if (startResult.workflow_id) {
        updatedDeployment.workflow_id = startResult.workflow_id;
      }
      set({ selectedDeployment: updatedDeployment });

      return updatedDeployment;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to create deployment";
      set({ error: message, wizardStep: "review" });
      errorToast(message);
      return null;
    }
  },

  startDeployment: async (deploymentId) => {
    try {
      const startResult = await BudUseCasesAPI.deployments.start(deploymentId);
      successToast("Deployment started");
      await get().fetchDeployment(deploymentId);
      // Attach workflow_id from start response for CommonStatus real-time tracking
      if (startResult.workflow_id) {
        const current = get().selectedDeployment;
        if (current && current.id === deploymentId) {
          set({ selectedDeployment: { ...current, workflow_id: startResult.workflow_id } });
        }
      }
      return true;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to start deployment";
      errorToast(message);
      return false;
    }
  },

  stopDeployment: async (deploymentId) => {
    try {
      await BudUseCasesAPI.deployments.stop(deploymentId);
      successToast("Deployment stopped");
      await get().fetchDeployment(deploymentId);
      return true;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to stop deployment";
      errorToast(message);
      return false;
    }
  },

  deleteDeployment: async (deploymentId) => {
    try {
      await BudUseCasesAPI.deployments.delete(deploymentId);
      successToast("Deployment deleted");
      set((state) => ({
        deployments: state.deployments.filter((d) => d.id !== deploymentId),
        selectedDeployment: state.selectedDeployment?.id === deploymentId ? null : state.selectedDeployment,
      }));
      return true;
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to delete deployment";
      errorToast(message);
      return false;
    }
  },

  syncDeploymentStatus: async (deploymentId) => {
    try {
      const deployment = await BudUseCasesAPI.deployments.sync(deploymentId);
      set({ selectedDeployment: deployment });
      // Update in list if present
      set((state) => ({
        deployments: state.deployments.map((d) => (d.id === deploymentId ? deployment : d)),
      }));
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to sync deployment status";
      errorToast(message);
    }
  },

  selectDeployment: (deployment) => {
    set({ selectedDeployment: deployment });
  },

  // -------------------------------------------------------------------------
  // Deployment Progress Polling
  // -------------------------------------------------------------------------

  pollDeploymentProgress: (deploymentId, intervalMs = 5000) => {
    // Stop any existing polling first and clear stale progress
    get().stopPollingDeploymentProgress();
    set({ deploymentProgress: null });

    const fetchProgress = async () => {
      try {
        const progress = await BudUseCasesAPI.deployments.getDeploymentProgress(deploymentId);
        set({ deploymentProgress: progress });

        // Auto-stop polling when execution reaches a terminal state
        const status = progress.execution?.status?.toLowerCase();
        if (status === "completed" || status === "failed" || status === "cancelled") {
          get().stopPollingDeploymentProgress();
          // Refresh deployment to get final state
          await get().fetchDeployment(deploymentId);
        }
      } catch (error: any) {
        // Silently ignore polling errors to avoid toast spam
        console.error("Failed to fetch deployment progress:", error);
      }
    };

    // Fetch immediately, then set up interval
    fetchProgress();
    const pollingId = setInterval(fetchProgress, intervalMs);
    set({ progressPollingId: pollingId });
  },

  stopPollingDeploymentProgress: () => {
    const { progressPollingId } = get();
    if (progressPollingId) {
      clearInterval(progressPollingId);
      set({ progressPollingId: null });
    }
  },

  // -------------------------------------------------------------------------
  // App Overlay
  // -------------------------------------------------------------------------

  openAppOverlay: (deployment) => {
    set({ selectedDeployment: deployment, isAppOverlayOpen: true });
  },

  closeAppOverlay: () => {
    set({ isAppOverlayOpen: false });
  },

  // -------------------------------------------------------------------------
  // Utility
  // -------------------------------------------------------------------------

  clearError: () => {
    set({ error: null });
  },
}));

export default useUseCases;
