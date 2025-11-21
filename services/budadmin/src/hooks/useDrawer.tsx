import { errorToast } from "@/components/toast";
import {
  FormProgressStatus,
  FormProgressType,
} from "@/components/ui/bud/progress/FormProgress";
import { StepComponentsType } from "src/flows";
import { create } from "zustand";
import drawerFlows, { Flow } from "./drawerFlows";
import { useAgentStore } from "@/stores/useAgentStore";
import { updateQueryParams } from "@/utils/urlUtils";

export type DrawerStepParsedType = {
  id: string;
  step: number;
  navigation: string[];
  component: React.FC;
  progress: FormProgressType[];
  properties?: any;
  confirmClose: boolean;
  status: FormProgressStatus;
};

export const useDrawer = create<{
  minmizedProcessList: {
    step: DrawerStepParsedType;
    flow: Flow;
  }[];
  showMinimizedItem: boolean;
  minimizeProcess: (step: DrawerStepParsedType) => void;
  maxmizedProcess: (step: DrawerStepParsedType) => void;
  isDrawerOpen: boolean;
  openDrawer: (newFlow: Flow, props?: any) => void;
  openDrawerWithStep: (step: string, props?: any) => void;
  openDrawerWithExpandedStep: (step: string, props?: any) => void;
  closeDrawer: () => void;
  currentFlow: Flow | null;
  setCurrentFlow: (flow: Flow) => void;
  step: DrawerStepParsedType;
  expandedStep: DrawerStepParsedType;
  previousStep?: StepComponentsType;
  setPreviousStep: (step: StepComponentsType) => void;
  cancelAlert: boolean;
  setCancelAlert: (value: boolean) => void;
  timeout?: NodeJS.Timeout;
  closeExpandedStep: () => void;
  isFailed: boolean;
  setFailed: (value: boolean) => void;
  drawerProps?: any;
  expandedDrawerProps?: any;
}>((set, get) => ({
  isFailed: false,
  setFailed: (value: boolean) => {
    set({ isFailed: value });
  },
  showMinimizedItem: false,
  minmizedProcessList: [],
  timeout: null,
  closeExpandedStep: () => {
    set({ expandedStep: null });
  },
  minimizeProcess: (step: DrawerStepParsedType) => {
    console.log("Minimizing process", step);
    get().timeout && clearTimeout(get().timeout);
    get().closeDrawer();
    set((state) => {
      return {
        // 1 item in the list
        minmizedProcessList: [
          {
            step: step,
            flow: get().currentFlow,
          },
        ],
        showMinimizedItem: true,
        cancelAlert: false,
        // Hide the minimized item after 5 seconds
        timeout: setTimeout(() => {
          set((state) => {
            return {
              showMinimizedItem: false,
            };
          });
        }, 3000),
      };
    });
  },
  maxmizedProcess: (step: DrawerStepParsedType) => {
    set((state) => {
      return {
        minmizedProcessList: state.minmizedProcessList.filter(
          (s) => s.step.id !== step.id,
        ),
        showMinimizedItem: false,
      };
    });
  },
  previousStep: null,
  expandedStep: null,
  setPreviousStep: (step: StepComponentsType) => {
    set({ previousStep: step });
  },
  isDrawerOpen: false,
  openDrawer: (newFlow: Flow, props: any) => {
    const foundStep = drawerFlows[newFlow].steps[0];
    set({
      isDrawerOpen: true,
      currentFlow: newFlow,
      cancelAlert: false,
      step: {
        ...foundStep,
        navigation: foundStep.navigation(),
        status: FormProgressStatus.inProgress,
      },
      expandedStep: null,
      isFailed: false,
      drawerProps: props,
      expandedDrawerProps: null,
    });
  },
  openDrawerWithExpandedStep: (step: string, props: any) => {
    const foundFlow = Object.keys(drawerFlows).find((flow) => {
      return drawerFlows[flow as Flow].steps.find((s) => s.id === step);
    }) as Flow;
    if (!foundFlow) {
      errorToast(`Flow not found for step ${step}`);
      return;
    }

    const foundFlowSteps = drawerFlows[foundFlow].steps;
    const foundStepIndex = foundFlowSteps.find((s) => s.id === step).step;
    const foundStep = foundFlowSteps.find((s) => s.id === step);

    if (!foundStepIndex) {
      errorToast("Step not found");
      return;
    }
    console.groupEnd();
    set({
      expandedStep: {
        ...foundStep,
        navigation: foundStep.navigation(),
        status: FormProgressStatus.inProgress,
      },
      expandedDrawerProps: props,
    });
  },
  openDrawerWithStep: (step: string, props: any) => {
    const foundFlow = Object.keys(drawerFlows).find((flow) => {
      return drawerFlows[flow as Flow].steps.find((s) => s.id === step);
    }) as Flow;
    if (!foundFlow) {
      errorToast(`Flow not found for step ${step}`);
      return;
    }

    const foundFlowSteps = drawerFlows[foundFlow].steps;
    const foundStepIndex = foundFlowSteps.find((s) => s.id === step).step;
    const foundStep = foundFlowSteps.find((s) => s.id === step);

    if (!foundStepIndex) {
      errorToast("Step not found");
      return;
    }
    console.groupEnd();
    set({
      isDrawerOpen: true,
      currentFlow: foundFlow,
      cancelAlert: false,
      step: {
        ...foundStep,
        navigation: foundStep.navigation(),
        status: FormProgressStatus.inProgress,
      },
      minmizedProcessList: [],
      expandedStep: null,
      isFailed: false,
      drawerProps: props,
      expandedDrawerProps: null,
    });
  },
  closeDrawer: () => {
    // Remove agent parameter from URL ONLY when closing add-agent flow
    const currentFlow = get().currentFlow;

    if (typeof window !== 'undefined' && currentFlow === 'add-agent') {
      const urlSearchParams = new URLSearchParams(window.location.search);
      const hasPromptParam = urlSearchParams.has('prompt');

      // Get AgentDrawer state synchronously - no setTimeout or dynamic import needed!
      const agentStoreState = useAgentStore.getState();
      const isAgentDrawerOpen = agentStoreState.isAgentDrawerOpen;
      const isTransitioning = agentStoreState.isTransitioningToAgentDrawer;

      // MULTI-LAYERED SAFETY CHECKS: Only remove agent parameter if ALL conditions are met:
      // 1. No prompt parameter in URL (not transitioning to/from AgentDrawer)
      // 2. AgentDrawer is not open (not in AgentDrawer)
      // 3. Not currently transitioning to AgentDrawer (flag set BEFORE closeDrawer)
      // 4. Currently in add-agent flow
      //
      // These checks ensure agent parameter is preserved when:
      // - User is in AgentDrawer (hasPromptParam = true)
      // - User is transitioning from AddAgent → AgentDrawer (isTransitioning = true)
      // - AgentDrawer is already open (isAgentDrawerOpen = true)
      if (!hasPromptParam && !isAgentDrawerOpen && !isTransitioning) {
        console.log('✓ Safe to remove agent parameter - no prompt and AgentDrawer not open/transitioning');

        // Add small delay to ensure any concurrent transitions have time to set their flags
        // This provides defense-in-depth against race conditions
        setTimeout(() => {
          // Re-check conditions after delay to be extra safe
          const currentUrlParams = new URLSearchParams(window.location.search);
          const stillHasPromptParam = currentUrlParams.has('prompt');
          const currentAgentState = useAgentStore.getState();

          // Only remove if conditions are still valid after delay
          if (!stillHasPromptParam && !currentAgentState.isAgentDrawerOpen && !currentAgentState.isTransitioningToAgentDrawer) {
            // Use shared utility function for URL manipulation
            updateQueryParams({ agent: null }, { replaceHistory: true });
            console.log('✓ Agent parameter removed after safety delay');
          } else {
            console.log('⚠️ Agent parameter preserved after delay check - conditions changed');
          }
        }, 100);
      } else {
        console.log('⚠️ Preserving agent parameter:', {
          hasPromptParam,
          isAgentDrawerOpen,
          isTransitioning,
          reason: hasPromptParam
            ? 'prompt parameter exists (in AgentDrawer)'
            : isTransitioning
              ? 'transitioning to AgentDrawer'
              : 'AgentDrawer is open'
        });
      }
    }

    set({
      isDrawerOpen: false,
      currentFlow: null,
      step: null,
      previousStep: null,
      expandedStep: null,
      isFailed: false,
      drawerProps: null,
      expandedDrawerProps: null,
    });
  },
  currentFlow: "run-model-evaluations",
  // currentFlow: "view-model",
  // currentFlow: "deploy-model",
  setCurrentFlow: (flow: Flow) => {
    set({ currentFlow: flow });
  },
  // get current flow
  step: null,
  progress: [],
  cancelAlert: false,
  setCancelAlert: (value: boolean) => {
    set({ cancelAlert: value });
  },
}));
