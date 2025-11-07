import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useContext, useEffect, useRef } from "react";
import Tags, { DropDownContent } from "src/flows/components/DrawerTags";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useState } from "react";
import { Model } from "src/hooks/useModels";
import { SpecificationTableItem } from "src/flows/components/SpecificationTableItem";
import { getSpecValueWidthOddEven } from "@/lib/utils";
import { assetBaseUrl, enableDevMode } from "@/components/environment";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import ModelTags from "src/flows/components/ModelTags";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { useDeployModel } from "src/stores/useDeployModel";
import { BranchType } from "../Advanced/Advanced";
import { Image } from "antd";
import { ChevronRight } from "lucide-react";
import { set } from "date-fns";

interface GeneralProps {
  data?: Model;
  goToAdapter?: boolean;
}

const General: React.FC<GeneralProps> = ({ data, goToAdapter }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { hasPermission } = useUser();
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const { openDrawerWithStep, openDrawer, openDrawerWithExpandedStep } =
    useDrawer();
  const { reset } = useDeployModel();

  const handleScrollToContainer = () => {
    if (containerRef.current) {
      containerRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };
  useEffect(() => {
    console.log("goToAdapter", goToAdapter);
  }, [goToAdapter]);

  useEffect(() => {
    if (goToAdapter) {
      handleScrollToContainer();
      setTimeout(() => {
        onDerivedCardClick({
          name: "Adapters",
          value: `${data?.quantizations_count} models`,
          color: "#B3B3B3",
          key: "adapter",
        });
      }, 500);
    }
  }, [goToAdapter]);

  const specs = [
    {
      icon: "/images/drawer/tag.png",
      name: "Device Name",
      value: data?.minimum_requirements?.device_name,
      type: "text",
    },
    {
      icon: "/images/drawer/tag.png",
      name: "Memory",
      value: data?.minimum_requirements?.memory,
      type: "text",
    },
    {
      icon: "/images/drawer/tag.png",
      name: "Number of Cores",
      value: data?.minimum_requirements?.core,
      type: "text",
    },
    {
      icon: "/images/drawer/tag.png",
      name: "RAM",
      value: data?.minimum_requirements?.RAM,
      type: "text",
    },
  ]?.filter((item) => item.value);

  const [isExpanded, setIsExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const descriptionRef = useRef(null);

  const toggleDescription = () => setIsExpanded(!isExpanded);

  useEffect(() => {
    if (descriptionRef.current) {
      const element = descriptionRef.current;
      setIsOverflowing(element.scrollHeight > 50);
    }
  }, [data?.description]);

  const onDerivedCardClick = (branch: BranchType) => {
    openDrawerWithExpandedStep("derived-model-list", {
      selectedBranch: branch,
      model: data,
    });
  };

  const SpecificationItem: React.FC<{
    name: string;
    data: React.ReactNode;
  }> = ({ name, data }) => {
    return (
      <div
        className={`flex items-center justify gap-[.4rem]`}
        style={{
          width: "100%",
          justifyContent: "flex-start",
        }}
      >
        <div className={`flex justify-start items-center ${"min-w-[32%]"}`}>
          <div className="h-[.75rem] flex justify-start items-start">
            <div className="!mr-[.4rem] w-[0.75rem] flex justify-start items-start">
              <Image
                preview={false}
                src="/images/drawer/tag.png"
                alt="info"
                style={{ height: ".75rem" }}
              />
            </div>
          </div>
          <Text_12_400_B3B3B3 className="ml-[.1rem] mr-[.4rem] text-nowrap">
            {name}
          </Text_12_400_B3B3B3>
        </div>
        <div
          className={`flex flex-row gap-[.4rem] max-w-full max-w-[50%]} text-left min-h-[1.5rem]`}
        >
          {data}
        </div>
      </div>
    );
  };

  return (
    <div className="pt-[.25rem]">
      {/* <ModelTags model={data} hideEndPoints hideTags showExternalLink /> */}
      <div className="">
        {data?.description ? (
          <>
            <div className="pt-[1.3rem]">
              <div
                ref={descriptionRef}
                className={`leading-[1.05rem] tracking-[.01em max-w-[100%] ${
                  isExpanded ? "" : "line-clamp-2"
                } overflow-hidden`}
                style={{ display: "-webkit-box", WebkitBoxOrient: "vertical" }}
              >
                <Text_12_400_B3B3B3 className="leading-[180%]">
                  {data?.description}
                </Text_12_400_B3B3B3>
              </div>
              {isOverflowing && (
                <div className="flex justify-end">
                  <Text_12_600_EEEEEE
                    className="cursor-pointer leading-[1.05rem] tracking-[.01em] mt-[.3rem]"
                    onClick={toggleDescription}
                  >
                    {isExpanded ? "See less" : "See more"}
                  </Text_12_600_EEEEEE>
                </div>
              )}
            </div>
            <div className="hR mt-[1.1rem]"></div>
          </>
        ) : (
          hasPermission(PermissionEnum.ModelManage) && (
            <>
              <div className="flex justify-between items-center pt-[1.3rem]">
                <div>
                  <Text_14_400_EEEEEE>Description</Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Description not available
                  </Text_12_400_757575>
                </div>
                <PrimaryButton
                  disabled={isExpandedViewOpen}
                  classNames="mt-[1rem]"
                  onClick={() => {
                    if (isExpandedViewOpen) return;
                    openDrawerWithStep("edit-model");
                  }}
                >
                  Add Description
                </PrimaryButton>
              </div>
              <div className="hR mt-[1.5rem]"></div>
            </>
          )
        )}
        <div>
          <div className="pt-[1.3rem]">
            <Text_14_400_EEEEEE>Modalities</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following is the list of things model is really good at doing
            </Text_12_400_757575>
            <div className="modality flex items-center justify-start gap-[.5rem] mt-[1rem]">
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Input
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.text.input
                          ? "/images/drawer/endpoints/text.png"
                          : "/images/drawer/endpoints/text-not.png"
                      }
                      alt={data.modality.text.label}
                      style={{ width: "1.25rem", height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.image.input
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={data.modality.image.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.audio.input
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={data.modality.audio.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%]">
                  {[
                    data.modality.text.input && data.modality.text.label,
                    data.modality.image.input && data.modality.image.label,
                    data.modality.audio.input && data.modality.audio.label,
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </Text_12_400_EEEEEE>
              </div>
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Output
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.text.output
                          ? "/images/drawer/endpoints/text.png"
                          : "/images/drawer/endpoints/text-not.png"
                      }
                      alt={data.modality.text.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.image.output
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={data.modality.image.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        data.modality.audio.output
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={data.modality.audio.label}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%]">
                  {[
                    data.modality.text.output && data.modality.text.label,
                    data.modality.image.output && data.modality.image.label,
                    data.modality.audio.output && data.modality.audio.label,
                  ]
                    .filter(Boolean)
                    .join(", ")}
                </Text_12_400_EEEEEE>
              </div>
            </div>
          </div>
          <div className="hR mt-[1.5rem]"></div>
        </div>
        <div>
          <div className="pt-[1.3rem]">
            <Text_14_400_EEEEEE>Supported Endpoints</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following is the list of things model is really good at doing
            </Text_12_400_757575>
            <div className="modality flex flex-wrap items-start justify-between gap-y-[.5rem] gap-x-[.75rem] mt-[1.5rem]">
              {Object.entries(data.supported_endpoints).map(([key, value]) => {
                const iconName = value.enabled
                  ? `${key}.png`
                  : `${key}-not.png`;
                return (
                  <div
                    key={key}
                    className="flex items-center justify-start gap-[.8rem] w-[calc(50%-0.4rem)] bg-[#ffffff08] p-[1rem] rounded-[6px]"
                  >
                    <div className="h-[1.25rem]">
                      <Image
                        preview={false}
                        src={`/images/drawer/endpoints/${iconName}`}
                        alt={value.label}
                        style={{ height: "1.25rem", width: "1.25rem" }}
                        onError={(e) => {
                          e.currentTarget.src = value.enabled
                            ? "/images/drawer/endpoints/default.png"
                            : "/images/drawer/endpoints/default-not.png";
                        }}
                      />
                    </div>
                    <div>
                      {value.enabled ? (
                        <>
                          <Text_14_400_EEEEEE>{value.label}</Text_14_400_EEEEEE>
                          <Text_12_400_B3B3B3 className="leading-[180%]">
                            {value.path}
                          </Text_12_400_B3B3B3>
                        </>
                      ) : (
                        <>
                          <Text_14_400_757575>{value.label}</Text_14_400_757575>
                          <Text_12_400_757575 className="leading-[180%]">
                            {value.path}
                          </Text_12_400_757575>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="hR mt-[1.5rem]"></div>
        </div>

        {data?.strengths?.length > 0 && (
          <>
            <div className="pt-[1.5rem] mb-[1.4rem]">
              <div>
                <Text_14_400_EEEEEE>Model is Great at</Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.45rem]">
                  Following is the list of things model is really good at doing
                </Text_12_400_757575>
              </div>
              <ul className="custom-bullet-list mt-[.9rem]">
                {data?.strengths?.map((item, index) => (
                  <li key={index}>
                    <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul>
            </div>
            <div className="hR"></div>
          </>
        )}
        {data?.limitations?.length > 0 && (
          <>
            <div className="pt-[1.5rem] mb-[1.4rem]">
              <div>
                <Text_14_400_EEEEEE>Model is Not Good With</Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.45rem]">
                  Following is the list of things model is not great at
                </Text_12_400_757575>
              </div>
              <ul className="custom-bullet-list mt-[.9rem]">
                {data?.limitations?.map((item, index) => (
                  <li key={index}>
                    <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                      {item}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul>
            </div>
            <div className="hR"></div>
          </>
        )}
        <div className="mt-[1.4rem] mb-[1.4rem]">
          <div className="flex justify-between items-center">
            <div>
              {!data?.model_licenses?.id && (
                <>
                  <Text_14_400_EEEEEE>License Details</Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    License details are not available
                  </Text_12_400_757575>
                </>
              )}
            </div>
            {!data?.model_licenses?.id &&
              hasPermission(PermissionEnum.ModelManage) && (
                <PrimaryButton
                  disabled={isExpandedViewOpen}
                  onClick={() => {
                    if (isExpandedViewOpen) return;
                    openDrawerWithStep("edit-model");
                  }}
                >
                  Add License
                </PrimaryButton>
              )}
          </div>
          {data?.model_licenses?.id && data?.model_licenses?.name && (
            <>
              {/* <Text_12_400_757575 className="pt-[.45rem]">
                Following are the details about the license
              </Text_12_400_757575> */}
              <div>
                <DropDownContent
                  classNames="z-[1]"
                  dropMessage={{
                    clickDisabled:
                      !data?.model_licenses.path && !data?.model_licenses.url,
                    title: data?.model_licenses.name,
                    description: data?.model_licenses?.description,
                    // description: "This is the license agreement for the model",
                    // actionLabel: "View License",
                    // onClick: () => {
                    //   if (data?.model_licenses.path) {
                    //     window
                    //       .open(
                    //         `${assetBaseUrl}${data?.model_licenses.path}`,
                    //         "_blank"
                    //       )
                    //       .focus();
                    //   } else if (data?.model_licenses.url) {
                    //     window.open(data?.model_licenses.url, "_blank").focus();
                    //   }
                    // },
                  }}
                  contentmessage={{
                    show: data?.model_licenses?.faqs?.length > 0,
                    messageContentclassNames: "z-[1]",
                    data: data?.model_licenses?.faqs,
                  }}
                />
              </div>
              {/* <div className="flex flex-col justify-start mt-[1.5rem] pb-[.2rem] gap-y-[1rem] hidden">
                <SpecificationItem
                  name="License Name"
                  data={
                    <Tags
                      name={data?.model_licenses.name}
                      color="#D1B854"
                      textClass="!text-[.75rem] whitespace-pre-line leading-snug relative testClasss"
                      dropPatentClasses="relative z-[1500]"
                      drop={
                        <DropDownContent
                          dropMessage={{
                            clickDisabled:
                              !data?.model_licenses.path &&
                              !data?.model_licenses.url,
                            title: data?.model_licenses.name,
                            description:
                              "This is the license agreement for the model",
                            actionLabel: "View License",
                            onClick: () => {
                              if (data?.model_licenses.path) {
                                window
                                  .open(
                                    `${assetBaseUrl}${data?.model_licenses.path}`,
                                    "_blank"
                                  )
                                  .focus();
                              } else if (data?.model_licenses.url) {
                                window
                                  .open(data?.model_licenses.url, "_blank")
                                  .focus();
                              }
                            },
                          }}
                          contentmessage={{
                            show: data?.model_licenses?.faqs?.length > 0,
                            messageContentclassNames: "",
                            data: data?.model_licenses?.faqs,
                          }}
                        />
                      }
                    />
                  }
                />
                {data?.model_licenses?.license_type && (
                  <SpecificationItem
                    name="Type"
                    data={
                      <Text_12_400_EEEEEE>
                        {data?.model_licenses?.license_type}
                      </Text_12_400_EEEEEE>
                    }
                  />
                )}
                {data?.model_licenses?.suitability && (
                  <SpecificationItem
                    name="Suitability"
                    data={
                      <Text_12_400_EEEEEE>
                        {data?.model_licenses?.suitability}
                      </Text_12_400_EEEEEE>
                    }
                  />
                )}
              </div> */}
            </>
          )}
        </div>
        <div className="hR"></div>
        {data?.use_cases?.length > 0 && (
          <>
            <div className="mt-[1.4rem] mb-[1.4rem]">
              <div className="flex justify-between items-center">
                <div>
                  <Text_14_400_EEEEEE>Suitable Use Cases</Text_14_400_EEEEEE>
                  {!data?.use_cases?.length && (
                    <Text_12_400_757575 className="pt-[.45rem]">
                      Use Cases not available
                    </Text_12_400_757575>
                  )}
                </div>
              </div>
              {data?.use_cases?.length && (
                <>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Following are some of the use cases this model has been used
                    for
                  </Text_12_400_757575>
                  <ul className="custom-bullet-list mt-[.9rem]">
                    {data?.use_cases?.map((item, index) => (
                      <li key={index}>
                        <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                          {item}
                        </Text_12_400_EEEEEE>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div className="hR"></div>
          </>
        )}
        {data?.languages?.length > 0 && (
          <>
            <div className="mt-[1.4rem] mb-[1.4rem]">
              <div className="flex justify-between items-center">
                <div>
                  <Text_14_400_EEEEEE>Languages</Text_14_400_EEEEEE>
                  {!data?.languages?.length && (
                    <Text_12_400_757575 className="pt-[.45rem]">
                      Languages not available
                    </Text_12_400_757575>
                  )}
                </div>
              </div>
              {data?.languages?.length && (
                <>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Following are some of the use languages this model has been
                    used for
                  </Text_12_400_757575>
                  <div className="flex flex-row gap-[.4rem] mt-[.9rem]">
                    {data?.languages?.map((item, index) => (
                      <Tags
                        key={index}
                        name={item}
                        color="#D1B854"
                        textClass="!text-[.75rem] whitespace-pre-line leading-snug"
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
            <div className="hR"></div>
          </>
        )}
        {enableDevMode && specs.length > 0 && (
          <div className="mt-[1.4rem] mb-[1.4rem]">
            <Text_14_400_EEEEEE>
              Minimum Hardware Specification
            </Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.45rem]">
              Here you can see the minimum hardware you require for optimal
              performance
            </Text_12_400_757575>
            <div className="pt-[.8rem] flex justify-between items-center flex-wrap gap-y-[1.5rem]">
              {specs.map((item, index) => (
                <SpecificationTableItem
                  key={index}
                  item={item}
                  valueWidth={getSpecValueWidthOddEven(specs, index)}
                />
              ))}
            </div>
          </div>
        )}
        <div className="hR"></div>

        {data?.provider_type !== "cloud_model" && (
          <div className="mt-[1.4rem] mb-[1.4rem]" ref={containerRef}>
            {enableDevMode && (
            <div
              className="w-full mb-[1rem] py-[1.5rem] px-[1rem] cursor-pointer bg-[#101010] hover:bg-[#1F1F1F]  border border-[#1F1F1F] rounded-[8px]"
              onClick={() =>
                onDerivedCardClick({
                  name: "Quantizations",
                  value: `${data?.quantizations_count} models`,
                  color: "#B3B3B3",
                  key: "quantized",
                })
              }
            >
              <div className="flex justify-start align-center mb-[0.5rem]">
                <Image
                  preview={false}
                  src={"/images/icons/modelRepoWhite.png"}
                  alt="info"
                  width={18}
                  height={18}
                />
                <Text_14_400_EEEEEE className="ml-[.5rem] mt-[-.1rem]">
                  Quantised Models
                </Text_14_400_EEEEEE>
              </div>
              <div className="flex justify-between items-center mt-[1rem]">
                <span className="text-[2.375rem] text-[#EEEEEE] leading-[100%] font-[400] relative">
                  {data?.quantizations_count}
                </span>
                <div
                  className={`items-center align-center text-[0.75rem] px-[0.8rem] py-[.3rem] cursor-pointer bg-[#1F1F1F] hover:bg-[#101010] border border-[#757575] rounded-[8px] text-[#EEEEEE] hover:text-[#EEEEEE] flex mr-[.6rem] whitespace-nowrap`}
                >
                  See More <ChevronRight className="h-[0.8rem]" width={16} />
                </div>
              </div>
            </div>)}
            <div
              className="w-full py-[1.5rem] px-[1rem] cursor-pointer bg-[#101010] hover:bg-[#1F1F1F]  border border-[#1F1F1F] rounded-[8px]"
              onClick={() =>
                onDerivedCardClick({
                  name: "Adapters",
                  value: `${data?.quantizations_count} models`,
                  color: "#B3B3B3",
                  key: "adapter",
                })
              }
            >
              <div className="flex justify-start align-center mb-[0.5rem]">
                <Image
                  preview={false}
                  src={"/images/icons/adapter.png"}
                  alt="info"
                  width={18}
                  height={18}
                />
                <Text_14_400_EEEEEE className="ml-[.5rem] mt-[-.1rem]">
                  Adapters
                </Text_14_400_EEEEEE>
              </div>
              <div className="flex justify-between items-center mt-[1rem]">
                <span className="text-[2.375rem] text-[#EEEEEE] leading-[100%] font-[400] relative">
                  {data?.adapters_count}
                </span>
                <div
                  className={`items-center align-center text-[0.75rem] px-[0.8rem] py-[.3rem] cursor-pointer bg-[#1F1F1F] hover:bg-[#101010] border border-[#757575] rounded-[8px] text-[#EEEEEE] hover:text-[#EEEEEE] flex mr-[.6rem] whitespace-nowrap`}
                >
                  See More <ChevronRight className="h-[0.8rem]" width={16} />
                </div>
              </div>
            </div>
          </div>
        )}

        {data?.examples?.length > 0 && (
          <>
            <div className="hR"></div>
            <div className="mt-[1.4rem] mb-[1.4rem]">
              <Text_14_400_EEEEEE>Examples</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="pt-[.9rem]">
                These could input output text or Images, Audio or video. This
                section is only shown if its available.
              </Text_12_400_757575>
              {data?.examples?.map((item, index) => (
                <div
                  key={index}
                  className="rounded-[8px] mt-[.7rem] px-[.9rem] py-[1.1rem] bg-[#FFFFFF08]"
                >
                  <div>
                    <Text_12_400_EEEEEE>Prompt</Text_12_400_EEEEEE>
                    {item.prompt_type == "string" && (
                      <div className="flex justify-between items-center px-[.9rem] py-[.7rem] border border-[#757575] rounded-[8px] mt-[.4rem]">
                        <Text_12_400_B3B3B3 className="leading-[1.05rem]">
                          {item?.prompt}
                        </Text_12_400_B3B3B3>
                      </div>
                    )}
                  </div>
                  <div className="mt-[1.7rem]">
                    <Text_12_400_EEEEEE>Output</Text_12_400_EEEEEE>
                    {item.response_type == "string" && (
                      <div className="flex justify-between items-center px-[.9rem] py-[.7rem] border border-[#757575] rounded-[8px] mt-[.4rem]">
                        <Text_12_400_B3B3B3 className="leading-[1.05rem]">
                          {item?.response}
                        </Text_12_400_B3B3B3>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
export default General;
