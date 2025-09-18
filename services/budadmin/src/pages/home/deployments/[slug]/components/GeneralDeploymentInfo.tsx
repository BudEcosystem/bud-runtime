import {
  Text_11_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import React, { useEffect, useRef, useState } from "react";
import { formatDate } from "src/utils/formatDate";
import DeploymentAnalysis from "./DeploymentAnalysis";
import CacheAnalysis from "./CacheAnalysis";
import TagsList from "src/flows/components/TagsList";
import { useEndPoints } from "src/hooks/useEndPoint";
import ModelTags from "src/flows/components/ModelTags";
import ClusterTags from "src/flows/components/ClusterTags";
import IconRender from "src/flows/components/BudIconRender";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useCluster } from "src/hooks/useCluster";
import router from "next/router";

function GeneralDeploymentInfo({
  switchTab,
}: {
  switchTab: (key: string) => void;
}) {
  const { clusterDetails } = useEndPoints();
  const { openDrawerWithStep } = useDrawer();
  const { getModel } = useModels();
  const { getClusterById } = useCluster();
  const descriptionRef = useRef(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleDescription = () => setIsExpanded(!isExpanded);

  useEffect(() => {
    if (descriptionRef.current) {
      const element = descriptionRef.current;
      setIsOverflowing(element.scrollHeight > 50);
    }
  }, [clusterDetails?.model?.description]);

  return (
    <div className="mt-[1.1rem] pl-[.15rem] relative">
      <div className="flex gap-[1rem]">
        <div
          className={`flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] ${clusterDetails?.model?.provider_type === "cloud_model" ? "w-full" : "w-[50%]"} bg-[#101010] cursor-pointer`}
          onClick={async (e) => {
            e.stopPropagation();
            const result = await getModel(clusterDetails?.model?.id);
            if (result) {
              openDrawerWithStep("view-model-details");
            }
          }}
        >
          <div className="w-full">
            <div className="flex items-start justify-start w-full">
              <IconRender
                icon={clusterDetails?.model?.icon}
                model={clusterDetails?.model}
                type={clusterDetails?.model.provider_type}
              />
              <div className="ml-[.75rem]">
                <span className="block text-[0.875rem] font-[400] text-[#EEEEEE] leading-[.875rem]">
                  {clusterDetails?.model?.name}
                </span>
                <Text_11_400_808080 className="mt-[.35rem]">
                  {formatDate(clusterDetails?.model?.created_at)}
                </Text_11_400_808080>
              </div>
            </div>
            <div className="mt-[.6rem]">
              <div className="flex items-center justify-start w-full">
                <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                  <ModelTags
                    hideEndPoints
                    maxTags={3}
                    model={clusterDetails?.model}
                    // showExternalLink showLicense
                  />
                </div>
              </div>
            </div>
            {clusterDetails?.model?.description && (
              <>
                <div className="">
                  <div
                    ref={descriptionRef}
                    className={`leading-[1.05rem] tracking-[.01em max-w-[100%] ${
                      isExpanded ? "" : "line-clamp-3"
                    } overflow-hidden`}
                    style={{
                      display: "-webkit-box",
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    <Text_12_400_B3B3B3 className="mt-[1.15rem] leading-[1.05rem]">
                      {clusterDetails?.model?.description}
                    </Text_12_400_B3B3B3>
                  </div>
                  {isOverflowing && (
                    <div className="flex justify-end">
                      <Text_12_600_EEEEEE
                        className="cursor-pointer leading-[1.05rem] tracking-[.01em] mt-[.3rem]"
                        onClick={(e) => {
                          toggleDescription();
                          e.stopPropagation();
                        }}
                      >
                        {isExpanded ? "See less" : "See more"}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Hide cluster detail card for cloud models */}
        {clusterDetails?.model?.provider_type !== "cloud_model" && (
          <div
            className="flex items-center  flex-col border  border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] w-[50%]  bg-[#101010] cursor-pointer"
            onClick={async (e) => {
              e.stopPropagation();
              await getClusterById(clusterDetails?.cluster?.id);
              router.push(`/clusters/${clusterDetails?.cluster?.id}`);
            }}
          >
            <div className="flex items-start justify-start w-full">
              <IconRender icon={clusterDetails?.cluster?.icon} />

              <div className="ml-[.75rem]">
                <span className="block text-[0.875rem] font-[400] text-[#EEEEEE] leading-[.875rem]">
                  {clusterDetails?.cluster?.name}
                </span>
                <Text_11_400_808080 className="mt-[.35rem]">
                  {formatDate(clusterDetails?.cluster?.created_at)}
                </Text_11_400_808080>
              </div>
            </div>
            <div className="mt-[.5rem] self-start">
              <div className="flex items-center justify-start w-full">
                <div>
                  <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                    <ClusterTags
                      hideEndPoints
                      cluster={clusterDetails?.cluster}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="flex flex-grow items-center justify-between mt-[0]" />
            <div className="text-[#B3B3B3] flex flex-col items-start justify-start gap-[.5rem] mt-4 w-full text-[.75rem]">
              <Text_12_400_EEEEEE className="mb-[.1rem]">
                Resource Availability
              </Text_12_400_EEEEEE>
              <div className="flex items-center justify-start gap-[.45rem]">
                <TagsList
                  data={[
                    {
                      name: `${clusterDetails?.cluster?.available_nodes || 0} Available Nodes`,
                      color: "#EEEEEE",
                    },
                    {
                      name: `${clusterDetails?.cluster?.total_nodes || 0} Total Nodes`,
                      color: "#EEEEEE",
                    },
                  ]}
                />
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="hR mt-[1.6rem]"></div>
      <div className="mt-[1rem]">
        <DeploymentAnalysis switchTab={switchTab} />
      </div>
      {/* <div className='hR mt-[1.45rem]'></div>
      <div className='mt-[1rem]'>
        <CacheAnalysis />
      </div> */}
      <div className="h-[4rem]" />
    </div>
  );
}

export default GeneralDeploymentInfo;
