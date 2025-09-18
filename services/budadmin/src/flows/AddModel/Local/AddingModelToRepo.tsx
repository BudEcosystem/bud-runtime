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
import { Image, Tag } from "antd"; // Added Checkbox import
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { LinkOutlined } from "@ant-design/icons";
import { SliderInput } from "@/components/ui/input";

const tags = [
  {
    name: "Model Link",
    color: "#D1B854",
    bg: "#423A1A40",
    image: true,
  },
  {
    name: "Author Name",
    color: "#D1B854",
    bg: "#423A1A40",
    image: false,
  },
];

function ModelTag({ tag }) {
  return (
    <Tag
      className={`border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem]`}
      style={{
        backgroundColor: getChromeColor(tag.bg),
      }}
    >
      {tag.image && (
        <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
          <LinkOutlined
            style={{
              color: tag.color || "#B3B3B3",
            }}
          />
        </div>
      )}
      <div
        className={`text-[0.625rem] font-[400] leading-[100%]`}
        style={{
          color: tag.color || "#B3B3B3",
        }}
      >
        {tag.name || tag}
      </div>
    </Tag>
  );
}

export default function AddingModelToRepo() {
  const { openDrawerWithStep } = useDrawer();
  const { submittable } = useContext(BudFormContext);
  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍",
      }}
      onNext={() => {
        openDrawerWithStep("select-or-add-credentials");
      }}
      nextText="Link API"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Model Information"
            description="Following is the information we have collected from the link you gave. Please verify it while we continue adding your model to the repository."
            classNames="pt-[1.1rem] pb-[1.4rem]"
          />
          <div>
            <div className="flex items-center justify-start w-full p-[1.35rem]">
              <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0">
                <Image
                  preview={false}
                  src="/images/drawer/zephyr.png"
                  alt="info"
                  style={{ width: "1.75rem" }}
                />
              </div>
              <div>
                <Text_14_400_EEEEEE className="mb-[0.65rem]">
                  Model Name
                </Text_14_400_EEEEEE>
                <div className="flex items-center justify-start flex-wrap">
                  {tags.map((item, index) => (
                    <ModelTag tag={item} key={index} />
                  ))}
                </div>
              </div>
            </div>
            <div className="px-[1.4rem] pt-[.1rem] mb-[1.1rem]">
              <Text_12_400_B3B3B3 className="leading-[1.05rem]">
                InternLM 2.5 offers strong reasoning across the board as well as
                tool use for developers, while sitting at the sweet spot of size
                for those with 24GB GPUs.
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Adding model to the repository"
            description="In process of verification, downloading and extracting the model"
            classNames="pt-[1.1rem] pb-[1.2rem]"
          />
          <div>
            <SliderInput
              defaultValue={[0.5]}
              max={1}
              step={0.1}
              className="border-[0] "
            ></SliderInput>
            <div className="flex flex-start! items-center! w-full px-[1.35rem] mt-[1.1rem] justify-start">
              <div className="flex justify-center items-center px-[.8rem] py-[.4rem] rounded-[21px] bg-[#1F1F1F]">
                <div className="w-[1rem] h-[1rem] mr-[.4rem]">
                  <Image
                    preview={false}
                    src="/images/drawer/clock.png"
                    alt="info"
                    style={{
                      width: "1rem",
                      height: "1rem",
                      marginRight: ".4rem",
                    }}
                  />
                </div>
                <Text_12_400_B3B3B3 className="leading-[100%] whitespace-nowrap">
                  Estimated Time
                </Text_12_400_B3B3B3>
                <Text_12_400_EEEEEE className="leading-[100%] ml-[.3rem] whitespace-nowrap">
                  {" "}
                  3 hrs 32 Mins 12 Sec
                </Text_12_400_EEEEEE>
              </div>
            </div>
            <div className="flex justify-start items-center px-[1.4rem] mt-[1.6rem] mb-[1.4rem]">
              <div className="mr-[0rem] w-[1.5rem] flex justify-start items-start">
                <Image
                  preview={false}
                  src="/images/drawer/load.png"
                  alt="info"
                  style={{ height: "1.5rem" }}
                />
              </div>
              <Text_12_400_EEEEEE className="ml-[.4rem]">
                Model Extraction
              </Text_12_400_EEEEEE>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
