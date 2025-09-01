import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import {
  Text_14_400_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
} from "@/components/ui/text";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import React, { useContext, useEffect, useState } from "react";
import CustomDropdownMenu, { BudDropdownMenu } from "@/components/ui/dropDown";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useCluster } from "src/hooks/useCluster";
import { errorToast } from "@/components/toast";
import { useDeployModel } from "src/stores/useDeployModel";
import { useCloudCredentials } from "src/stores/useCloudCredentials";
import { Image } from "antd";
import Tags from "src/flows/components/DrawerTags";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";

export default function ConfigureClusterDetails() {
  const { values, submittable } = useContext(BudFormContext);
  const { openDrawerWithStep } = useDrawer();
  const { createClusterWorkflow, clusterValues, setClusterValues, cloudID } =
    useCluster();
  const { getWorkflow } = useDeployModel();
  const { selectedCredential } = useCloudCredentials();
  const [formData, setFormData] = React.useState<FormData>(new FormData());

  const { getRegionByProviderID, isLoading } = useCloudInfraProviders();

  const [regions, setRegions] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await getRegionByProviderID(cloudID);
        const regionsMap = response.map((region: { id: any; name: any }) => ({
          value: region.id,
          label: region.name,
        }));
        setRegions(regionsMap);
      } catch (error) {
        console.error("Error fetching region data:", error);
      }
    };

    if (cloudID) {
      fetchData();
    }
  }, [cloudID, getRegionByProviderID]);

  useEffect(() => {
    formData.set("step_number", "1");
    formData.set("workflow_total_steps", "3");
    formData.set("trigger_workflow", "true");
    formData.set("name", values.name || "");
    formData.set("icon", values.icon || "😍");
    formData.set("region", values.region || "");
    formData.set("cluster_type", "CLOUD");

    // CredentialID
    formData.set("credential_id", selectedCredential);
    formData.set("provider_id", cloudID);
  }, [values]);

  return (
    <BudForm
      data={{
        icon: "😍",
        ...clusterValues,
      }}
      onBack={() => openDrawerWithStep("choose-cloud-credential")}
      onNext={async (values) => {
        const result = await createClusterWorkflow(formData);
        if (result) {
          await getWorkflow(result.workflow_id);
          openDrawerWithStep("create-cluster-status");
        } else {
          errorToast("Error creating cluster");
        }
      }}
      disableNext={!clusterValues.name || !clusterValues.region}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Configure Cluster Details"
            description="Enter the details for your new Kubernetes cluster"
          />

          <DrawerCard classNames="pb-0">
            <div className="pt-[.87rem]">
              <ProjectNameInput
                placeholder="Enter Cluster Name"
                isEdit={true}
              />

              <div className="height-26" />

              <div className="mb-[1.7rem]">
                <BudDropdownMenu
                  name="region"
                  label="Region"
                  infoText="Select the region where your cluster will be deployed"
                  placeholder="Select a region"
                  items={regions}
                  value={clusterValues.region || undefined}
                  onSelect={() => {}}
                  onChange={(value) => {
                    console.log(value);
                    setClusterValues({ ...clusterValues, region: value });
                    setFormData((prev) => {
                      prev.set("region", value);
                      return prev;
                    });
                  }}
                />
              </div>
            </div>
            <div className="px-[1.4rem]  rounded-md border-[.5px] border-[#1F1F1F]">
              <div className="py-[1.2rem]">
                <Text_14_400_EEEEEE>Node Information</Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.45rem] pb-[1rem]">
                  Specifications of the nodes in your cluster
                </Text_12_400_757575>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-[.6rem]">
                    <div className="w-[2rem] h-[2rem] flex items-center justify-center bg-[#1E1E1E] rounded-md">
                      <Image
                        preview={false}
                        src="/images/icons/Desktop.png"
                        alt="Node"
                        width={20}
                        height={20}
                      />
                    </div>
                    <div>
                      <Text_14_400_EEEEEE>Standard_D2s_v3</Text_14_400_EEEEEE>
                      <Text_12_400_757575>1 Node</Text_12_400_757575>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
