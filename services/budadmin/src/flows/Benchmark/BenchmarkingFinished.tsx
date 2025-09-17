import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useProjects } from "src/hooks/useProjects";
import { useDeployModel } from "src/stores/useDeployModel";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { StepComponentsType } from "..";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "../components/SpecificationTableItem";
import { capitalize, getFormattedToBillions } from "@/lib/utils";
import { Image } from "antd"; // Added Checkbox import
import { Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";

export default function BenchmarkingFinished() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const [models, setModels] = React.useState([]);

  const { loading, fetchModels } = useModels();
  const [search, setSearch] = React.useState("");
  const { selectedProjectId } = useProjects();
  const {
    selectedModel,
    currentWorkflow,
    createWorkflow,
    updateModel,
    setSelectedModel,
  } = useDeployModel();
  const {
    openDrawerWithStep,
    openDrawer,
    setPreviousStep,
    currentFlow,
    step,
    closeDrawer,
  } = useDrawer();

  useEffect(() => {}, []);

  return (
    <BudForm
      data={{}}
      // disableNext={!selectedModel?.id}
      onNext={async () => {
        closeDrawer();
      }}
      nextText="View Report"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col	justify-start items-center p-[2.5rem] pt-[5.5rem]">
            <div className="align-center">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="info"
                width={140}
                height={129}
              />
            </div>
            <div className="mt-[1.3rem] mb-[3rem] w-full flex justify-center items-center flex-col	">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
                Benchmark successful
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center leading-[1.125rem] max-w-[85%]">
                We have successfully completed the benchmark, please view the
                report for the details
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
