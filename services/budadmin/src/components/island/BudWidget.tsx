import { Flex, Image, Progress, Spin } from "antd";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { WorkflowListItem, WorkflowType } from "src/stores/useWorkflow";
import {
  Text_10_400_757575,
  Text_10_400_B3B3B3,
  Text_12_400_A4A4A9,
  Text_14_600_EEEEEE,
} from "../ui/text";
import { capitalize, formdateDateTime } from "@/lib/utils";
import Tags from "src/flows/components/DrawerTags";
import drawerFlows, {
  DrawerFlowType,
  DrawerStepType,
  flowMapping,
  inProgressSteps,
} from "src/hooks/drawerFlows";
import { useProjects } from "src/hooks/useProjects";
import { useModels } from "src/hooks/useModels";
import { useIsland } from "src/hooks/useIsland";
import { errorToast } from "../toast";
import { FormProgressStatus } from "../ui/bud/progress/FormProgress";
import { calculateEta } from "src/flows/utils/calculateETA";
import IconRender from "src/flows/components/BudIconRender";
import { useEvaluations } from "@/hooks/useEvaluations";
import { useAddAgent } from "@/stores/useAddAgent";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export function getFailedStep(data: WorkflowListItem) {
  return data?.progress?.steps?.find(
    (step) => step.payload?.content?.status === "FAILED",
  );
}

export function getCurrentStep(data: WorkflowListItem) {
  return data?.progress?.steps?.find(
    (step) =>
      step.payload?.content?.status === "PENDING" ||
      step.payload?.content?.status === "RUNNING" ||
      step.payload?.content?.status === "FAILED" ||
      !step.payload?.content?.status,
  );
}

export function getActiveProgress(step: DrawerStepType) {
  return step?.progress?.find(
    (progress) => progress.status === FormProgressStatus.inProgress,
  );
}

export function getCurrentFlowStep(
  data: WorkflowListItem,
  flow: DrawerFlowType,
) {
  let step = flow?.steps.find((step) => step.step === data.current_step);
  if (!step) {
    // if the step is not found, open the first step
    step = flow?.steps?.[0];
  }
  return step;
}

export function getWorkflowTypeConverted(workflowType: string) {
  return workflowType
    ?.split("_")
    ?.map((word) => capitalize(word))
    ?.join(" ");
}

export function BudWidget({
  data,
  index,
}: {
  data?: WorkflowListItem;
  index: number;
}) {
  const { setSelectedProject } = useProjects();
  const { setSelectedModel: setSelectedModelGlobal } = useModels();
  const {
    getWorkflow,
    setProviderType,
    setSelectedTemplate,
    setSelectedProvider,
    setSelectedModel,
    getWorkflowCloud,
    setDeploymentSpecification,
    setLocalModelDetails,
    setCloudModelDetails,
    setDeploymentCluster,
    setSelectedCredentials,
  } = useDeployModel();

  const { getWorkflow: getEvaluationWorkflow } = useEvaluations();
  const { getWorkflow: getAgentWorkflow } = useAddAgent();
  const { getWorkflow: getBenchmarkWorkflow } = usePerfomanceBenchmark();
  const { openDrawerWithStep } = useDrawer();
  const { close } = useIsland();
  const [loading, setLoading] = useState(false);

  const flowId = flowMapping[data.workflow_type];
  const flow: DrawerFlowType = drawerFlows[flowId];

  const faiedStep = getFailedStep(data);
  //PENDING, RUNNING, COMPLETED, FAILED
  const currentStep = getCurrentStep(data);

  // const currentStatus = `${faiedStep?.payload?.content?.status || currentStep?.payload?.content?.status || widgetData?.status}`
  const step = getCurrentFlowStep(data, flow);

  const activeProgress = getActiveProgress(step);
  let title: React.ReactNode =
    currentStep?.title || activeProgress?.title || flow?.title;

  if (
    data?.progress?.steps?.find((step) => step.id === "ranking") &&
    data.current_step === 6
  ) {
    // Special case
    title =
      data?.progress?.recommended_cluster_count > 0
        ? "Choose Cluster"
        : "Cluster Not Found";
  } else if (inProgressSteps.includes(step?.id) && data.progress) {
    title = (
      <>
        Estimated Time{" "}
        <span className="text-[#EEEEEE]">
          {calculateEta(data.progress.eta)}
        </span>
      </>
    );
  } else {
    title = (
      <>
        Continue from <span className="text-[#EEEEEE]">{title}</span>
      </>
    );
  }

  useEffect(() => {
    console.log("data.workflow_type", data.workflow_type);
  }, [data.workflow_type]);

  useEffect(() => {
    console.log("flowMapping", flowMapping);
  }, []);

  // useEffect(() => {
  //     console.log('index', index)
  // }, [index]);

  useEffect(() => {
    console.log("flow", flow);
  }, [flow]);

  const openWidget = async () => {
    let workflow: WorkflowType;
    console.log('WorkflowType data', data)
    setLoading(true);
    if (data.workflow_type === "model_deployment") {
      workflow = await getWorkflowCloud(data.id);
    } else {
      workflow = await getWorkflow(data.id);
    }

    if (data.workflow_type === "evaluate_model") {
      workflow = await getEvaluationWorkflow(data.id);
    }

    if (data.workflow_type === "prompt_creation") {
      workflow = await getAgentWorkflow(data.id);
    }

    if (data.workflow_type === "model_benchmark") {
      workflow = await getBenchmarkWorkflow(data.id);
    }
    setLoading(false);
    if (workflow.workflow_steps) {
      setProviderType(workflow.workflow_steps.provider_type);
      setSelectedProvider(workflow.workflow_steps.provider);
      setSelectedTemplate(workflow.workflow_steps.template);
      setSelectedModel(
        workflow.workflow_steps.model || workflow.workflow_steps.cloud_model,
      );
      setSelectedProject(workflow.workflow_steps.project);
      setSelectedModelGlobal(
        workflow.workflow_steps.model || workflow.workflow_steps.cloud_model,
      );
      setDeploymentSpecification({
        // Provide defaults for all required fields first, then spread saved config
        concurrent_requests: 0,
        avg_context_length: 0,
        avg_sequence_length: 0,
        per_session_tokens_per_sec: [],
        ttft: [],
        e2e_latency: [],
        ...workflow.workflow_steps.deploy_config,
        deployment_name: workflow.workflow_steps.endpoint_name || "",
      });
      setCloudModelDetails({
        ...workflow.workflow_steps.model,
      });
      setLocalModelDetails({
        ...workflow.workflow_steps.model,
      });
      setDeploymentCluster({
        ...workflow.workflow_steps.cluster,
      });
      setSelectedCredentials({
        ...workflow.workflow_steps.credential,
      });
    }
    console.log('WorkflowType', workflow)

    // resovles the workflow type to the flow id and get the flow details
    if (!flow) {
      errorToast(`Flow not found for ${data.workflow_type}`);
      return;
    }

    // Handle benchmark step 2 specially - check eval_with to determine correct step
    let stepId = step?.id;
    if (data.workflow_type === "model_benchmark" && data.current_step === 2 && workflow?.workflow_steps) {
      const evalWith = (workflow.workflow_steps as any).eval_with;
      if (evalWith === "configuration") {
        stepId = "add-Configuration";
      } else if (evalWith === "dataset") {
        stepId = "add-Datasets";
      }
    }

    openDrawerWithStep(stepId);
    close();
    // openDrawerWithStep(currentStepId);
  };

  return (
    <div
      className="item rounded-[1rem] px-[1.45rem] py-[1.45rem] box-border	bg-[#101010] width-full cursor-pointer hover:bg-[#161616] transition-all duration-300 overflow-hidden item"
      onClick={openWidget}
    >
      {<Spin className="z-[999999]" spinning={loading} fullscreen />}
      <div className="flex justify-between items-start">
        <div className="flex justify-start items-center">
          <IconRender icon={data?.icon} size={38} imageSize={24} />
          <div className="pt-[.3rem] ml-[.55rem]">
            <Text_12_400_A4A4A9 className="tracking-[-.01rem]">
              {/* #{index + 1}  */}
              {data?.title || flow?.title}
            </Text_12_400_A4A4A9>
            {/* <Text_14_600_EEEEEE className="tracking-[-.01rem]">{currentStep?.description || `${flow?.title} In Progress`}</Text_14_600_EEEEEE> */}
            <Text_14_600_EEEEEE className="tracking-[-.01rem]">{`${data?.title || flow?.title} ${faiedStep ? "Failed" : "In Progress"}`}</Text_14_600_EEEEEE>
          </div>
        </div>
        <div className="flex flex-col items-end justify-start">
          {faiedStep ? (
            <div className="relative mb-[1.4rem]">
              <Text_10_400_757575 className="absolute top-[-.1rem] right-[0] text-nowrap">
                {formdateDateTime(new Date(data?.modified_at))}
              </Text_10_400_757575>
            </div>
          ) : (
            <div className="relative mb-[1.4rem]">
              <Text_10_400_757575 className="absolute top-[-.1rem] right-[0] text-nowrap !text-[#B3B3B3]">
                {formdateDateTime(new Date(data?.modified_at))}
              </Text_10_400_757575>
            </div>
          )}
          {data.tag && <Tags name={data.tag} color={faiedStep && "#EC7575"} />}
        </div>
      </div>
      {data?.current_step && data?.total_steps && (
        <div className="mt-[1.5rem]">
          <div className="relative bg-[transparent] mb-1">
            <Progress
              strokeLinecap="butt"
              percent={(data?.current_step / data?.total_steps) * 100}
              showInfo={false}
              size={{ height: 3 }}
              strokeColor={faiedStep ? "#C94444" : "#965CDE"}
              trailColor={"#1F1F1F"}
            />
            <div
              className="absolute top-[100%] left-[2px]"
              style={{
                transform: "translateY(-7px)",
                width: `${(data?.current_step / data?.total_steps) * 100 - 1}%`,
                backgroundColor: faiedStep ? "#C94444" : "#965CDE",
                boxShadow: `0 0 15px 2px ${faiedStep ? "#C94444" : "#965CDE"}`,
                borderRadius: "4px",
              }}
            ></div>
          </div>
          <div className="flex justify-between items-center pt-[0.2rem]">
            <div className="flex justify-start items-center">
              {faiedStep && (
                <div className=" w-[.75rem] h-[.75rem] mr-[0.4rem] shrink-0 grow-0 flex justify-center items-center">
                  <Image
                    preview={false}
                    src="/images/drawer/xCut.png"
                    alt="info"
                    style={{ width: ".75rem" }}
                  />
                </div>
              )}
              <Text_10_400_B3B3B3>{title}</Text_10_400_B3B3B3>
            </div>
            <Text_10_400_B3B3B3>
              Step {data.current_step}/{data.total_steps}
            </Text_10_400_B3B3B3>
          </div>
        </div>
      )}
      {faiedStep && (
        <div className="flex justify-start items-center border border-[#361519] bg-[#952F2F26] backdrop-blur-[4px] rounded-[6px] mt-[1.5rem] px-[.3rem] pl-[.8rem]  py-[.4rem]">
          <Image
            preview={false}
            src="/images/drawer/danger.png"
            alt="info"
            width={"1rem"}
            height={"1rem"}
          />
          <div className="ml-[.75rem] text-[.75rem] text-[#E82E2E] font-[300] truncate w-[90%]">
            {faiedStep?.payload?.content?.title ||
              faiedStep?.payload?.content?.message ||
              "Failed"}
          </div>
        </div>
      )}
    </div>
  );
}
