import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { successToast } from "@/components/toast";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "../components/BudStepAlert";
import CommonStatus from "../components/CommonStatus";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export default function BenchmarkingProgress() {
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);

  const { currentWorkflow, cancelBenchmarkWorkflow } = usePerfomanceBenchmark();
  const { openDrawerWithStep, closeDrawer } = useDrawer();

  return (
    <BudForm
      data={{}}
      onBack={() => {
        if (isFailed) {
          closeDrawer();
        } else {
          setShowAlert(true);
        }
      }}
      backText="Cancel"
    >
      <BudWraperBox>
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warining"
              title="You're about to cancel the benchmark"
              description="Please note that if you cancel now, you will have to start the process again."
              cancelText="Continue Benchmark"
              confirmText="Cancel Anyways"
              confirmAction={async () => {
                if (currentWorkflow?.workflow_id) {
                  const response = await cancelBenchmarkWorkflow(
                    currentWorkflow.workflow_id,
                  );
                  if (response) {
                    successToast("Benchmark cancelled successfully");
                    closeDrawer();
                    return;
                  }
                }
                closeDrawer();
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
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
