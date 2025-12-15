import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import CommonStatus from "../components/CommonStatus";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export default function BenchmarkingProgress() {
  const [isFailed, setIsFailed] = React.useState(false);

  const { currentWorkflow } = usePerfomanceBenchmark();
  const { openDrawerWithStep, closeDrawer } = useDrawer();

  return (
    <BudForm
      data={{}}
      onBack={() => {
        closeDrawer();
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
            openDrawerWithStep("Benchmarking-Finished");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="performance_benchmark"
          title={"Benchmarking in Progress"}
          description="We've started performance benchmark. This process may take a while, depending on the benchmark"
        />
      </BudWraperBox>
    </BudForm>
  );
}
