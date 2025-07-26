import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useRouter } from "next/router";
import { IEndPoint, useEndPoints } from "src/hooks/useEndPoint";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { Text_12_300_EEEEEE, Text_12_400_757575, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import { Image } from "antd";
import Tags from "src/flows/components/DrawerTags";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { IconOnlyRender } from "src/flows/components/BudIconRender";
import { errorToast } from "@/components/toast";

const capitalize = (str) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

export default function SelectFallbackDeployment() {
  const router = useRouter();
  const { drawerProps, closeDrawer } = useDrawer();
  const [searchValue, setSearchValue] = useState("");
  const [selectedDeployment, setSelectedDeployment] = useState<IEndPoint | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const { endPoints, getEndPoints, loading } = useEndPoints();

  // Get current deployment ID from drawer props
  const currentDeploymentId = drawerProps?.currentDeploymentId;

  // Extract project ID from router
  const projectId = router.query.projectId ||
    (router.asPath.includes('/projects/')
      ? router.asPath.split('/projects/')[1]?.split('/')[0]
      : null);

  useEffect(() => {
    // Load deployments when component mounts
    const loadDeployments = async () => {
      if (projectId) {
        try {
          setLoadError(null);
          await getEndPoints({
            id: projectId as string,
            page: 1,
            limit: 100,
            name: searchValue,
            order_by: '-created_at',
          });
        } catch (error) {
          console.error('Error loading deployments:', error);
          const errorMessage = 'Failed to load deployments. Please try again.';
          setLoadError(errorMessage);
          errorToast(errorMessage);
        }
      }
    };

    // Debounce search
    const timer = setTimeout(() => {
      loadDeployments();
    }, searchValue ? 300 : 0);

    return () => clearTimeout(timer);
  }, [projectId, searchValue, getEndPoints]);

  // Filter out current deployment
  const availableDeployments = endPoints?.filter(
    deployment => deployment.id !== currentDeploymentId
  ) || [];

  const handleDeploymentSelect = (deployment: IEndPoint) => {
    // Only allow selection of running deployments
    if (deployment.status === 'running') {
      setSelectedDeployment(deployment);
    } else if (deployment.status !== 'running') {
      errorToast(`Cannot select deployment with status: ${deployment.status}. Only running deployments can be used as fallbacks.`);
    }
  };

  const handleConfirmSelection = () => {
    if (selectedDeployment && drawerProps?.onSelect) {
      drawerProps.onSelect(selectedDeployment);
    }
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedDeployment}
      onNext={handleConfirmSelection}
      nextText="Select Deployment"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Fallback Deployment"
            description="Choose a deployment to use as fallback when the primary deployment is unavailable"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <DrawerCard>
            <div className="mb-4">
              <SearchHeaderInput
                placeholder="Search deployments by name"
                searchValue={searchValue}
                expanded
                setSearchValue={setSearchValue}
                classNames="border border-[.5px] border-[#757575]"
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center justify-start gap-[.2rem]">
                <Text_12_400_757575>
                  Available Deployments&nbsp;
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>{availableDeployments.length}</Text_12_600_EEEEEE>
              </div>
            </div>
          </DrawerCard>

          <div className="">
            {loading ? (
              <div className="flex justify-center items-center py-8">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-8 h-8 border-2 border-[#965CDE] border-t-transparent rounded-full animate-spin"></div>
                  <Text_12_300_EEEEEE>Loading deployments...</Text_12_300_EEEEEE>
                </div>
              </div>
            ) : loadError ? (
              <div className="flex justify-center items-center min-h-[4rem] py-8">
                <div className="text-center">
                  <Text_12_300_EEEEEE className="text-[#FF6B6B]">{loadError}</Text_12_300_EEEEEE>
                  <button
                    onClick={() => {
                      setLoadError(null);
                      if (projectId) {
                        getEndPoints({
                          id: projectId as string,
                          page: 1,
                          limit: 100,
                          name: searchValue,
                          order_by: '-created_at',
                        });
                      }
                    }}
                    className="mt-2 px-3 py-1 text-xs text-[#965CDE] hover:text-[#7A4BC7] border border-[#965CDE] hover:border-[#7A4BC7] rounded transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : !projectId ? (
              <div className="flex justify-center items-center min-h-[4rem] py-8">
                <Text_12_300_EEEEEE className="text-[#FF6B6B]">Unable to determine project. Please try again.</Text_12_300_EEEEEE>
              </div>
            ) : availableDeployments.length > 0 ? (
              availableDeployments.map((deployment: IEndPoint) => (
                <div
                  key={deployment.id}
                  onClick={() => handleDeploymentSelect(deployment)}
                  className={`py-[.85rem] px-[1.4rem] border-b-[0.5px] border-t-[0.5px] flex-row flex items-start ${
                    deployment.status !== 'running'
                      ? 'opacity-50 cursor-not-allowed border-t-[transparent] border-b-[#1F1F1F]'
                      : selectedDeployment?.id === deployment.id
                        ? 'bg-[#FFFFFF0A] border-[#965CDE] border-t-[#965CDE] cursor-pointer hover:shadow-lg'
                        : 'border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg'
                  }`}
                >
                  <div className="mr-[1rem] flex flex-col justify-center">
                    <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[.52rem] flex justify-center items-center grow-0 shrink-0">
                      <IconOnlyRender
                        icon={deployment.model?.icon}
                        model={deployment.model}
                        type={deployment.model?.provider_type}
                        imageSize={27}
                      />
                    </div>
                  </div>

                  <div className="flex-auto max-w-[87%]">
                    <div className="flex items-center justify-between max-w-[100%]">
                      <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
                        <Text_14_400_EEEEEE className="leading-[100%]">
                          {deployment.name}
                        </Text_14_400_EEEEEE>
                        {deployment.status && (
                          <ProjectTags
                            name={capitalize(deployment.status)}
                            color={endpointStatusMapping[capitalize(deployment.status)]}
                            textClass="text-[.625rem]"
                          />
                        )}
                        {deployment.status !== 'running' && (
                          <div className="text-[#FF6B6B] text-xs">
                            (Not available)
                          </div>
                        )}
                        <div className="flex justify-start items-center gap-[.5rem]">
                          {deployment.cluster?.name && (
                            <Tags
                              name={deployment.cluster.name}
                              color="#D1B854"
                              classNames="py-[.32rem]"
                              textClass="leading-[100%] text-[.625rem] font-[400]"
                            />
                          )}
                        </div>
                      </div>
                      {selectedDeployment?.id === deployment.id && (
                        <div className="w-[1rem] h-[1rem] rounded-full bg-[#965CDE] flex items-center justify-center">
                          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                            <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </div>
                      )}
                    </div>
                    <Text_12_300_EEEEEE className="overflow-hidden truncate max-w-[95%]">
                      {deployment.model?.name || 'No model information'}
                    </Text_12_300_EEEEEE>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex justify-center items-center min-h-[4rem] py-8">
                <div className="text-center">
                  <Text_12_300_EEEEEE>No other deployments available in this project</Text_12_300_EEEEEE>
                  <Text_12_300_EEEEEE className="text-[#757575] mt-2">
                    Deploy more models to use them as fallbacks
                  </Text_12_300_EEEEEE>
                </div>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
