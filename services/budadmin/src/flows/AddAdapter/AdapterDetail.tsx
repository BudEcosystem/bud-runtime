import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { AdapterInfoCard } from "./AdapterInfoCard";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useContext, useEffect } from "react";
import { useDeployModel } from "src/stores/useDeployModel";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import TextInput from "../components/TextInput";
import { useRouter } from "next/router";

export const AdapterDetail = () => {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { values, form } = useContext(BudFormContext);
  const {
    updateAdapterDetailWorkflow,
    adapterWorkflow,
    setAdapterWorkflow,
    currentWorkflow,
  } = useDeployModel();
  const router = useRouter();
  const projectId = router.query.projectId as string;

  useEffect(() => {
    if (!currentWorkflow) {
      return;
    }
    setAdapterWorkflow({
      adapterModelId:
        currentWorkflow.workflow_steps.adapter_config?.adapter_model_id,
      adapterName: currentWorkflow.workflow_steps.adapter_config?.adapter_name,
      endpointId: currentWorkflow.workflow_steps.adapter_config?.endpoint_id,
      adapterId: currentWorkflow.workflow_steps.adapter_config?.adapter_id,
    });
  }, [currentWorkflow]);

  const handleNext = async () => {
    // form.submit();
    const result = await updateAdapterDetailWorkflow(
      adapterWorkflow?.adapterName,
      projectId,
    );
    if (!result) {
      return;
    }
    // setQuantizationWorkflow(values);
    openDrawerWithStep("add-adapter-status");
  };

  return (
    <BudForm
      data={adapterWorkflow}
      nextText="Next"
      onNext={handleNext}
      // disableNext={!selectedModel}
      backText="Back"
      onBack={() => {
        openDrawerWithStep("add-adapter-select-model");
      }}
    >
      <BudWraperBox>
        <AdapterInfoCard />
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Adapter Details"
            description="Enter the adapter deployment details"
            classNames="border-[0] border-b-[.5px]"
          />
          <DrawerCard>
            <TextInput
              name="adapterName"
              label="Adapter deployment name"
              placeholder="Enter adapter deployment name"
              rules={[
                { required: true, message: "Please enter deployment name" },
              ]}
              ClassNames="mt-[.4rem]"
              infoText="Enter a name for the deployment of the adapter"
              onChange={(e) =>
                setAdapterWorkflow({ ...adapterWorkflow, adapterName: e })
              }
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};
