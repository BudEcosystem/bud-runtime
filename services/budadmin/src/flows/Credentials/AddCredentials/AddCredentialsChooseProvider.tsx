import { errorToast } from "@/components/toast";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect } from "react";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { useProprietaryCredentials } from "src/stores/useProprietaryCredentials";

export default function AddCredentials() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const { selectedProvider, setSelectedProvider } = useProprietaryCredentials();
  const { getProviders, providers } = useCloudProviders();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { currentWorkflow, updateProvider } = useDeployModel();
  const { credentials, getCredentials, setSelectedCredential, selectedCredential, getProviderInfo } = useProprietaryCredentials();

  useEffect(() => {
    getProviders(page, limit, search);
  }, [page, limit, search, getProviders]);

  const filteredProviders = providers?.filter((provider) =>
    provider.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <BudForm
      data={{}}
      disableNext={!selectedProvider?.id}
      onNext={async () => {
        const providerInfoSuccess = await getProviderInfo(selectedProvider?.type);
        if (providerInfoSuccess) {
          openDrawerWithStep("add-credentials-form");
        } else {
          errorToast("Error fetching provider info");
          console.error("Failed to fetch provider info.");
        }
        return;
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Credentials"
            description="Please select the provider for which you would like to add credentials"
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
