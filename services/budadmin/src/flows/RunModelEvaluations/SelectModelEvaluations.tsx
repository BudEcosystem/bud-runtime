import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useContext } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd"; // Added Checkbox import
import SelectModel from "../components/SelectModel";
import Tags from "../components/DrawerTags";
import { useModels } from "src/hooks/useModels";
import TagsList from "../components/TagsList";

const tags = [
  {
    icon: "",
    name: "LLM",
    color: "#D1B854",
    background: "#423A1A40",
  },
  {
    icon: "",
    name: "7B",
    color: "#D1B854",
    background: "#423A1A40",
  },
  {
    icon: "",
    name: "Reasoning",
    color: "#D1B854",
    background: "#423A1A40",
  },
  {
    icon: "",
    name: "Task 1",
    color: "#4077E6",
    background: "#1B325140",
  },
  {
    icon: "",
    name: "Task 2",
    color: "#4077E6",
    background: "#1B325140",
  },
  {
    icon: "",
    name: "Paper 1",
    color: "#D1B854",
    background: "#423A1A40",
  },
  {
    icon: "",
    name: "Paper 1",
    color: "#EC7575",
    background: "#861A1A33",
  },
  {
    icon: "/images/drawer/github.png",
    name: "Github Link",
    color: "#965CDE",
    background: "#8F55D62B",
  },
  {
    icon: "/images/drawer/huggingface.png",
    name: "Huggingface Link",
    color: "#965CDE",
    background: "#8F55D62B",
  },
  {
    icon: "/images/drawer/websiteLink.png",
    name: "Website Link",
    color: "#965CDE",
    background: "#8F55D62B",
  },
  // {
  //   icon: '/images/drawer/websiteLink.png',
  //   name: 'Licence Name',
  //   color: '#965CDE',
  //   background: '#8F55D62B'
  // },
];

export default function SelectModelEvaluations() {
  const { submittable } = useContext(BudFormContext);
  const { closeDrawer, openDrawerWithStep, openDrawer } = useDrawer();
  const { getModel } = useModels();
  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍",
      }}
      onBack={() => {
        closeDrawer();
      }}
      onNext={() => {
        openDrawerWithStep("select-cluster-evaluations");
      }}
      backText="Skip"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex justify-start w-full p-[1.35rem] items-start">
            <div className="p-[.6rem] w-[2.75rem] h-[2.75rem] bg-[#1F1F1F] rounded-[6px] flex justify-center align-center mr-[1.05rem] shrink-0 grow-0">
              <Image
                preview={false}
                src="/images/drawer/zephyr.png"
                alt="info"
                style={{ width: "1.75rem" }}
              />
            </div>
            <div>
              <div className="flex justify-between items-start">
                <Text_14_400_EEEEEE className="">
                  InternLM 2.5
                </Text_14_400_EEEEEE>
                <div
                  className="w-[.75rem] h-[.75rem] cursor-pointer"
                  onClick={async () => {
                    // await getModel(currentWorkflow?.workflow_steps?.model?.id);
                    // openDrawer("edit-model");
                  }}
                >
                  <Image
                    preview={false}
                    src="/images/drawer/edit.png"
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-start flex-wrap gap-[.45rem] gap-y-[.7rem] mt-[.6rem]">
                <TagsList data={tags} />
              </div>
            </div>
          </div>
          <div className="px-[1.4rem] pt-[.25rem] border-b-[1px] border-b-[#1F1F1F] pb-[.9rem]">
            <div className="flex justify-start items-center">
              <div className="flex justify-start items-center mr-[3.3rem]">
                <div className="w-[.75rem] h-[.75rem] flex justify-center align-center mr-[.5rem] shrink-0 grow-0">
                  <Image
                    preview={false}
                    src="/images/drawer/calander.png"
                    alt="info"
                    style={{ width: ".75rem" }}
                  />
                </div>
                <Text_12_400_B3B3B3>Updated on</Text_12_400_B3B3B3>
              </div>
              <Text_12_400_EEEEEE>3rd July, 2024</Text_12_400_EEEEEE>
            </div>
            <Text_12_400_B3B3B3 className="mt-[1.2rem] leading-[1.1rem]">
              InternLM 2.5 offers strong reasoning across the board as well as
              tool use for developers, while sitting at the sweet spot of size
              for those with 24GB GPUs.
            </Text_12_400_B3B3B3>
          </div>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Run Model Evaluations"
            description="Choose one or more model evaluations to verify the performance benchmarks. This will help you understand the strengths and the weakness of the model."
          />
          <SelectModel />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
