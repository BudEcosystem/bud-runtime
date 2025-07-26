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
import { SpecificationTableItem, SpecificationTableItemProps } from "../components/SpecificationTableItem";
import { capitalize, getFormattedToBillions } from "@/lib/utils";
import CommonStatus from "../components/CommonStatus";
import { successToast } from "@/components/toast";
import { time } from "console";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export default function BenchmarkingProgress() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const [models, setModels] = React.useState([]);
  const [isFailed, setIsFailed] = React.useState(false);

  const {
    loading,
    fetchModels
  } = useModels();
  const [search, setSearch] = React.useState("");
  const { selectedProjectId } = useProjects();
  const { currentWorkflow } = usePerfomanceBenchmark();
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step, closeDrawer } = useDrawer();



  return (
    <BudForm
      data={{}}
      onBack={async () => {
        openDrawerWithStep("simulate-run");
      }}
      backText="Cancel"
    >

      <BudWraperBox>
        {/* <BudDrawerLayout>
          <DrawerTitleCard
            title="Benchmarking in Progress"
            description="Description"
            classNames="pt-[.8rem] pb-[1.2rem]"
            descriptionClass="pt-[.3rem]"
          />

        </BudDrawerLayout> */}
        <CommonStatus
            workflowId={currentWorkflow?.workflow_id}
            events_field_id="budserve_cluster_events"
            onCompleted={() => {
              closeDrawer();
              successToast("Cluster deleted successfully");
            }}
            onFailed={() => {
              setIsFailed(true);
            }}
            success_payload_type="performance_benchmark"
            title={"Benchmarking in Progress"}
            description="We’ve started performance benchmark. This process may take a while, depending on the benchmark"
          />
      </BudWraperBox>
    </BudForm>
  );
}
