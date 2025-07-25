import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";
import { useCluster } from "src/hooks/useCluster";

export default function CloudChooser() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const { setCloudID, cloudID } = useCluster();

  const { getProviders, providers } = useCloudInfraProviders();

  useEffect(() => {
    getProviders();
  }, [getProviders]);

  return (
    <BudForm
      data={{}}
      onNext={() => {
        // Navigate to the appropriate next step based on selected provider
        if (selectedProvider) {
          setCloudID(selectedProvider);
          // console.log(`Selected Provider ID: ${selectedProvider}`);
          openDrawerWithStep("choose-cloud-credential");
        }
      }}
      disableNext={!selectedProvider}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Choose Cloud Provider"
            description="Select the cloud provider where you want to deploy your Kubernetes cluster"
          />

          <div className="pt-[.4rem]">
            {providers &&
              providers.map((provider, index) => (
                <ProviderCardWithCheckBox
                  key={index}
                  data={provider}
                  selected={selectedProvider === provider.id}
                  handleClick={() => {
                    setSelectedProvider(provider.id);
                  }}
                />
              ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
