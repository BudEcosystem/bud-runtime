import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "../components/SpecificationTableItem";
import { capitalize, getFormattedToBillions } from "@/lib/utils";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { Button } from "antd";
import { EditOutlined } from "@ant-design/icons";

export default function BenchmarkConfiguration() {
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } =
    useDrawer();
  const { stepSix, currentWorkflow, stepSeven, getWorkflow } = usePerfomanceBenchmark();
  const [workflowData, setWorkflowData] = useState<any>(
    currentWorkflow?.workflow_steps,
  );

  // Refresh workflow data on mount
  useEffect(() => {
    getWorkflow().then(() => {
      setWorkflowData(currentWorkflow?.workflow_steps);
    });
  }, []);

  let architectureArrayAdditional: SpecificationTableItemProps[] = [
    {
      name: "Cluster Name",
      value: [workflowData?.cluster?.name],
      // value: [`${getFormattedToBillions(12)}`],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Node Name",
      value: workflowData?.nodes?.map((node) => node.hostname) || [],
      // value: [capitalize(`${'name'}`)],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Model Name",
      value: [workflowData?.model?.name],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    // {
    //   name: 'Concurrent Request',
    //   value: '',
    //   full: true,
    //   icon: "/images/drawer/tag.png",
    //   children: []
    // },
    {
      name: "Eval with",
      value: [workflowData?.eval_with],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Dataset/ Config nam.",
      value: [workflowData?.name],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "No. of Nodes Selected",
      value: [`${workflowData?.nodes?.length} Nodes`],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "No. of Workers",
      value: [
        workflowData?.cluster?.cpu_total_workers
          ? `${workflowData?.cluster?.cpu_total_workers} in CPU`
          : null,
        workflowData?.cluster?.gpu_total_workers
          ? `${workflowData?.cluster?.gpu_total_workers} in GPU`
          : null,
        workflowData?.cluster?.hpu_total_workers
          ? `${workflowData?.cluster?.hpu_total_workers} in HPU`
          : null,
      ].filter(Boolean),
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Hardware Type",
      value: [workflowData?.cluster?.cluster_type],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Tags",
      value: workflowData?.tags?.map((node) => node.name) || [],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
  ];

  // Configuration options items (displayed separately with edit button)
  const configurationItems: SpecificationTableItemProps[] = [
    {
      name: "Device Type",
      value: workflowData?.selected_device_type
        ? [workflowData.selected_device_type.toUpperCase()]
        : [],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "TP/PP Configuration",
      value:
        workflowData?.tp_size !== undefined && workflowData?.pp_size !== undefined
          ? [`TP=${workflowData.tp_size}, PP=${workflowData.pp_size}`]
          : [],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Replicas",
      value: workflowData?.replicas ? [`${workflowData.replicas}`] : [],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
    {
      name: "Number of Prompts",
      value: workflowData?.num_prompts ? [`${workflowData.num_prompts}`] : ["Default (dataset samples)"],
      full: true,
      icon: "/images/drawer/tag.png",
      children: [],
    },
  ];

  const hasConfiguration =
    workflowData?.selected_device_type ||
    workflowData?.tp_size !== undefined ||
    workflowData?.replicas;

  useEffect(() => {
    console.log("workflowData", workflowData);
  }, [workflowData]);

  useEffect(() => {
    setWorkflowData(currentWorkflow?.workflow_steps);
  }, [currentWorkflow]);

  useEffect(() => {
    stepSix().then((result) => {
      console.log("result", result);
    });
  }, []);

  return (
    <BudForm
      data={{}}
      onBack={async () => {
        openDrawerWithStep("Select-Configuration");
      }}
      onNext={() => {
        stepSeven().then((result) => {
          openDrawerWithStep("simulate-run");
        });
      }}
      nextText="Confirm"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Benchmark Configuration"
            description="Verify the configuration you have selected for performing the benchmark"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <div className="mt-[1.1rem] flex flex-col gap-y-[1.15rem] mb-[1.1rem] px-[1.4rem]">
            {architectureArrayAdditional
              .filter(
                (item) =>
                  Array.isArray(item.value) &&
                  item.value.length > 0 &&
                  item.value.some(Boolean),
              )
              .map((item, index) => (
                <SpecificationTableItem
                  key={index}
                  item={item}
                  tagClass="py-[.26rem] px-[.4rem]"
                  benchmark={true}
                />
              ))}

            {/* Configuration Options Section */}
            {hasConfiguration && (
              <>
                <div className="flex items-center justify-between mt-4 mb-2">
                  <span className="text-[#B3B3B3] text-[12px] font-medium">
                    Deployment Configuration
                  </span>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => openDrawerWithStep("Select-Configuration")}
                    className="text-[#5B9FFF] hover:text-[#7BB3FF]"
                  >
                    Edit
                  </Button>
                </div>
                {configurationItems
                  .filter(
                    (item) =>
                      Array.isArray(item.value) &&
                      item.value.length > 0 &&
                      item.value.some(Boolean),
                  )
                  .map((item, index) => (
                    <SpecificationTableItem
                      key={`config-${index}`}
                      item={item}
                      tagClass="py-[.26rem] px-[.4rem]"
                      benchmark={true}
                    />
                  ))}
              </>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
