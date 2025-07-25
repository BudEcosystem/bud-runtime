
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect } from "react";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useCloudProviders } from "src/hooks/useCloudProviders";

import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function ModelCloudProviders() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const { selectedProvider, setSelectedProvider, deleteWorkflow } = useDeployModel();
  const { getProviders, providers } = useCloudProviders();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { currentWorkflow, updateProvider } = useDeployModel();

  useEffect(() => {
    getProviders(page, limit, search);
  }, []);

  const filteredProviders = providers?.filter((provider) => provider.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <BudForm
      data={{
      }}
      onBack={async () => {
        await deleteWorkflow(currentWorkflow.workflow_id, true);
        openDrawerWithStep("model-source");
      }}
      disableNext={!selectedProvider?.id}
      onNext={async () => {
        if (!currentWorkflow) {
          return openDrawerWithStep("model-source");
        } else {
          await updateProvider();
        }
        openDrawerWithStep("model-list");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select a Cloud Provider"
            description="Pick one provider and start adding their models to the model repository."
          />
          <div className="px-[1.5rem] mt-[1.5rem]">
            <SearchHeaderInput
              placeholder="Search Providers"
              searchValue={search}
              setSearchValue={setSearch}
              expanded
            />
          </div>
          <div className="pt-[.4rem]">
            {filteredProviders?.map((item, index) => (
              <ProviderCardWithCheckBox
                key={index}
                data={item}
                selected={selectedProvider?.id === item.id}
                handleClick={() => {
                  setSelectedProvider(item);
                }}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
