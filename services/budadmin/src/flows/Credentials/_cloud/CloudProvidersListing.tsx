import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { useCloudCredentials } from "src/stores/useCloudCredentials";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";

export default function CloudProvidersListing() {
  const { closeDrawer, openDrawerWithStep } = useDrawer();
  const [search, setSearch] = React.useState("");

  const { setSelectedProvider, selectedProvider } = useCloudCredentials();
  const { providers, getProviders, isLoading, error } =
    useCloudInfraProviders();

  // Fetch providers on component mount
  useEffect(() => {
    getProviders();
  }, [getProviders]);

  // Determine which providers to display (API data or fallback)

  return (
    <BudForm
      data={{}}
      onNext={async () => {
        openDrawerWithStep("add-cloud-credential-form");
      }}
      nextText="Next"
      disableNext={!selectedProvider}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Connect To Cloud Providers"
            description="Please select the provider for which you would like to add credentials"
          />

          {isLoading ? (
            <div className="pt-[.4rem]">Loading providers...</div>
          ) : error ? (
            <div className="pt-[.4rem]">Error loading providers: {error}</div>
          ) : (
            <div className="pt-[.4rem]">
              {providers &&
                providers.map((item, index) => (
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
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
