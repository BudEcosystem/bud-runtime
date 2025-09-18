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

export default function BenchmarkConfiguration() {
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } =
    useDrawer();
  const { stepSix, currentWorkflow, stepSeven } = usePerfomanceBenchmark();
  const [workflowData, setWorkflowData] = useState<any>(
    currentWorkflow?.workflow_steps,
  );

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

  useEffect(() => {
    console.log("workflowData", workflowData);
  }, [workflowData]);

  useEffect(() => {
    stepSix().then((result) => {
      console.log("result", result);
    });
  }, []);

  return (
    <BudForm
      data={{}}
      // disableNext={!selectedModel?.id}
      onBack={async () => {
        openDrawerWithStep("Select-Model");
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
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
