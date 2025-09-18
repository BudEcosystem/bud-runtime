import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { use, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import {
  ModelNameInput,
  NameIconInput,
} from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import { isValidModelName } from "@/lib/utils";
import CustomSelect from "../components/CustomSelect";
import { Image } from "antd";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import Tags from "../components/DrawerTags";

export default function SimulationDetails() {
  const { openDrawerWithStep } = useDrawer();
  const {
    currentWorkflow,
    updateModelDetailsLocal,
    updateCredentialsLocal,
    localModelDetails,
    deleteWorkflow,
  } = useDeployModel();
  const { values, form } = useContext(BudFormContext);
  const [hover, setHover] = React.useState(false);

  const statusOptions = [
    {
      value: "value 1",
      label: "value 1",
    },
    {
      value: "value 2",
      label: "value 2",
    },
  ];

  return (
    <BudForm
      data={localModelDetails}
      onBack={async () => {
        openDrawerWithStep("hardware-pecifications");
      }}
      onNext={async () => {
        openDrawerWithStep("simulation-details");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            className={`py-[1.5rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.5rem] flex-row flex items-start border-box`}
          >
            <div className="mr-[1rem] flex flex-col justify-center">
              <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[.52rem] flex justify-center items-center grow-0 shrink-0">
                <Image
                  preview={false}
                  src="/images/drawer/zephyr.png"
                  style={{ width: "1.67969rem", height: "1.67969rem" }}
                  alt="home"
                />
              </div>
            </div>
            <div className="flex-auto max-w-[91%]">
              <div className="flex items-center justify-between max-w-[100%]">
                <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
                  <Text_14_400_EEEEEE className="leading-[100%]">
                    Hardware name
                  </Text_14_400_EEEEEE>
                  <Tags
                    name="Website Link"
                    color="#965CDE"
                    classNames="pt-[.1rem] pb-[0]"
                    onTagClick={() => {
                      window.open(
                        "https://www.intel.com/content/www/us/en/events/on-event-series/vision.html",
                        "_blank",
                      );
                    }}
                    image={
                      <Image
                        preview={false}
                        src="/images/drawer/websiteLink.png"
                        className="mr-[0.375rem]"
                        style={{ width: "0.625rem", height: "0.625rem" }}
                        alt="home"
                      />
                    }
                  />
                </div>
              </div>
              <Text_12_400_757575 className="overflow-hidden truncate max-w-[95%]">
                Need to add hardware description here, to add hardware
                descrip...
              </Text_12_400_757575>
            </div>
          </div>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <div
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            className={`py-[1.5rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.5rem] flex-row flex items-start border-box`}
          >
            <div className="flex-auto max-w-[91%]">
              <div className="flex items-center justify-between max-w-[100%]">
                <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
                  <Text_14_400_EEEEEE className="leading-[100%]">
                    Hardware name
                  </Text_14_400_EEEEEE>
                </div>
              </div>
              <Text_12_400_757575 className="overflow-hidden truncate max-w-[95%]">
                Need to add hardware description here, to add hardware
                descrip...
              </Text_12_400_757575>
              <div className="flex justify-start items-center gap-[.5rem] mt-[1rem]">
                <Tags
                  name="Chat (QA)"
                  color="#D1B854"
                  classNames="pt-[.4rem] pb-[.3rem]"
                />
              </div>
            </div>
          </div>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={"Simulation Details"}
            description="Description for Simulation Details"
          />
          <DrawerCard classNames="">
            <TextInput
              name="SimulationName"
              label={"Simulation Name"}
              placeholder={"Enter Simulation Name"}
              rules={[{ message: "Please Simulation Name" }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[1.25rem]"
              infoText={"Enter Simulation Name"}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
