import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";

export default function ChooseCloudSource() {
  const { openDrawerWithStep, openDrawer } = useDrawer();
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  // Static options for cluster source
  const clusterOptions = [
    {
      id: "existing",
      name: "Connect to Existing Cluster",
      description: "Connect to an already deployed Kubernetes cluster",
      icon: "images/drawer/compare.png",
      iconLocal: true,
    },
    {
      id: "new",
      name: "Create New Cluster",
      description: "Deploy a new Kubernetes cluster on your cloud provider",
      icon: "images/drawer/textToSpeach.png",
      iconLocal: true,
    },
  ];

  return (
    <BudForm
      data={{}}
      onNext={() => {
        if (selectedOption === "existing") {
          openDrawer("add-cluster");
        } else if (selectedOption === "new") {
          openDrawer("add-cluster-select-provider");
        }
      }}
      disableNext={!selectedOption}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Choose Cluster Source"
            description="Select how you want to set up your Kubernetes cluster"
          />

          <div className="pt-[.4rem]">
            {clusterOptions.map((option, index) => (
              <ProviderCardWithCheckBox
                key={index}
                data={option}
                selected={selectedOption === option.id}
                handleClick={() => {
                  setSelectedOption(option.id);
                }}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
