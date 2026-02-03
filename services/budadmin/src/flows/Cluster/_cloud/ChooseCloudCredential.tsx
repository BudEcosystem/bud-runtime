import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useEffect, useState } from "react";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { useCloudCredentials } from "src/stores/useCloudCredentials";
import NoDataFount from "@/components/ui/noDataFount";

export default function ChooseCloudCredentialStep() {
  const { cloudID } = useCluster();
  const { selectedCredential, setSelectedCredential } = useCloudCredentials();
  const { openDrawerWithStep } = useDrawer();
  // const [selectedCredential, setSelectedCredential] = useState<string | null>(
  //   null,
  // );
  const {
    getProviders,
    providers,
    isLoading,
    getCloudCredentials,
    credentials,
  } = useCloudInfraProviders();

  useEffect(() => {
    if (!providers.length) {
      getProviders();
    }

    getCloudCredentials({
      providerId: cloudID,
    });
  }, [cloudID, getProviders, getCloudCredentials, providers.length]);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  const selectedProvider = providers.find(
    (provider) => provider.id === cloudID,
  );

  return (
    <BudForm
      data={{}}
      onNext={() => {
        if (selectedCredential) {
          openDrawerWithStep("configure-cluster-details");
        }
      }}
      onBack={() => {
        openDrawerWithStep("add-cluster-select-provider");
      }}
      disableNext={!selectedCredential}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={`Select Cloud Credential For ${selectedProvider.name}`}
            description="Select a cloud credential to proceed!"
          />

          <div className="pt-[.4rem]">
            {credentials && credentials.length > 0 ? (
              credentials.map((credential, index) => (
                <ProviderCardWithCheckBox
                  key={index}
                  data={{
                    id: credential.id,
                    name: credential.credential_name, //selectedProvider.name,
                    description: selectedProvider.description,
                    icon: selectedProvider.logo_url,
                    created_at: credential.created_at,
                  }}
                  selected={selectedCredential === credential.id}
                  handleClick={() => {
                    setSelectedCredential(credential.id);
                  }}
                />
              ))
            ) : (
              <NoDataFount
                classNames="min-h-[70px] text-center p-[2rem]"
                textMessage={`No credentials found for ${selectedProvider?.name || 'this provider'}. Please add credentials first.`}
              />
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
