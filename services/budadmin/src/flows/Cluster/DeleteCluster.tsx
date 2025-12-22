import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "../components/BudStepAlert";
import { successToast } from "@/components/toast";
import { useCluster } from "src/hooks/useCluster";

export default function DeleteCluster() {
  const { closeDrawer } = useDrawer();
  const { selectedCluster, deleteCluster, refresh } = useCluster();

  return (
    <BudForm data={{}}>
      <BudWraperBox>
        <BudDrawerLayout>
          <BudStepAlert
            type="warning"
            title="You're about to delete the cluster"
            description="You are about to delete the cluster. Once deleted, you won’t be able to recover. Please confirm, if you would like to proceed."
            confirmText="Delete Cluster"
            cancelText="Cancel"
            confirmAction={async () => {
              const result = await deleteCluster(selectedCluster?.id);
              if (result) {
                successToast("Cluster deleted successfully");
                await refresh();
              }
              closeDrawer();
            }}
            cancelAction={() => {
              closeDrawer();
            }}
          />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
