import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useProjects } from "src/hooks/useProjects";
import { Image } from "antd";
import { Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import dayjs from "dayjs";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { axiosInstance } from "src/pages/api/requests";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { MessageContent, MessageTop } from "./components/DrawerTags";
import { Model, useModels } from "src/hooks/useModels";
import { assetBaseUrl } from "@/components/environment";
import { useRef } from "react";

export default function LicenseDetails() {
  const { createProject, getProjects, getProject, projectValues } =
    useProjects();
  const { form, submittable } = useContext(BudFormContext);
  const [data, setdata] = useState<GeneralProps["data"]>();
  const { openDrawerWithStep, closeDrawer, previousStep, setPreviousStep } =
    useDrawer();
  const { selectedModel } = useModels();
  const messageContentRef = useRef<HTMLDivElement>(null);

  interface GeneralProps {
    data?: Model;
  }
  useEffect(() => {
    setdata(selectedModel);
  }, [selectedModel]);

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍",
      }}
      backText={previousStep ? "Back" : undefined}
      onBack={
        previousStep
          ? () => {
              if (previousStep) {
                openDrawerWithStep(previousStep);
                setPreviousStep(null);
              }
            }
          : undefined
      }
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={selectedModel.model_licenses.name}
            description={data?.model_licenses?.description}
          />
          <DrawerCard classNames="pb-0">
            <MessageTop
              actionLabel="View LICENSE file"
              onClick={() => {
                if (data?.model_licenses?.data_type == "url") {
                  window.open(
                    `${assetBaseUrl}${data?.model_licenses?.url}`,
                    "_blank",
                  );
                } else {
                  messageContentRef.current?.scrollIntoView({
                    behavior: "smooth",
                    block: "end",
                  });
                }
              }}
              classNames="w-full bg-[transparent]"
              showAll={true}
            />
            <MessageContent
              ref={messageContentRef}
              show={selectedModel.model_licenses?.faqs?.length > 0}
              data={selectedModel.model_licenses?.faqs}
              showAll={true}
              file={selectedModel.model_licenses}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
