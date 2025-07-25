
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd"; // Added Checkbox import
import ProprietaryCredentialsFormList from "../components/ProprietaryCredentialsFormList";
import { useDeployModel } from "src/stores/useDeployModel";
import { useModels } from "src/hooks/useModels";

const tags = [
  {
    icon: '/images/drawer/huggingface.png',
    name: 'OpenAI',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Together.ai',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Provider name',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Provider name',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Provider name',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Provider name',
    color: '#D1B854',
    background: '#423A1A40'
  },
  {
    icon: '/images/drawer/huggingface.png',
    name: 'Provider name',
    color: '#D1B854',
    background: '#423A1A40'
  },
]


export default function SelectCredentials() {
  const { closeDrawer } = useDrawer()
  const { selectedCredentials } = useDeployModel();
  const { selectedModel } = useModels();
  const providerType = selectedModel?.provider?.type;


  return (
    <BudForm
      disableNext={selectedCredentials === null}
      data={{
      }}
      onNext={() => {
        closeDrawer();
      }}
      onBack={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex justify-start w-full p-[1.35rem] items-start">
            <div className="p-[.6rem] w-[2.75rem] h-[2.75rem] bg-[#1F1F1F] rounded-[6px] flex justify-center align-center mr-[1.05rem] shrink-0 grow-0">
              <Image
                preview={false}
                src="/images/drawer/zephyr.png"
                alt="info"
                style={{ width: '1.75rem' }}
              />
            </div>
            <div>
              <div className="flex justify-between items-start">
                <Text_14_400_EEEEEE className="mb-[0.65rem]">
                  InternLM 2.5
                </Text_14_400_EEEEEE>
                <div className="w-[.75rem] h-[.75rem] cursor-pointer">
                  <Image
                    preview={false}
                    src="/images/drawer/edit.png"
                    alt="info"
                    style={{ width: '.75rem', height: '.75rem' }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                {tags?.map((tag, index) => (
                  <div
                    key={index}
                    style={{
                      backgroundColor: `${tag.background}`,
                      color: '#EEEEEE',
                    }}
                    className="text-[0.625rem]  font-[400] rounded-[6px] px-[.3rem] py-[.2rem] leading-[100%] flex justify-center items-center"
                  >
                    <div className="bg-[#1F1F1F] w-[0.75rem] h-[0.75rem] rounded-[5px] flex justify-center items-center grow-0 shrink-0 mr-[.35rem]">
                      <Image
                        preview={false}
                        src={tag.icon}
                        className="!w-[.75rem] !h-[.75rem]"
                        style={{ width: '.75rem', height: '.75rem' }}
                        alt="home"
                      />
                    </div>
                    <span className={`text-[0.625] font-[400]`}
                      style={{
                        color: `${tag.color}`
                      }}
                    >
                      {tag.name}
                    </span>
                  </div>
                ))}
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
                    style={{ width: '.75rem' }}
                  />
                </div>
                <Text_12_400_B3B3B3>Updated on</Text_12_400_B3B3B3>
              </div>
              <Text_12_400_EEEEEE>
                3rd July, 2024
              </Text_12_400_EEEEEE>
            </div>
            <Text_12_400_B3B3B3 className="mt-[1.2rem] leading-[1.1rem]">
              InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.
            </Text_12_400_B3B3B3>
          </div>
          <div className="px-[1.4rem] pt-[1.1rem] mb-[1.2rem]">
            <Text_14_600_EEEEEE>Evaluation Information</Text_14_600_EEEEEE>
            <div className="flex justify-start items-center flex-wrap	mt-[1.2rem] gap-[.5rem]">
              <div className="text-[#D1B854] text-[0.625rem] font-[400] bg-[#423A1A40] rounded-[6px] px-[.4rem] py-[.15rem]">MMLU</div>
              <div className="text-[#D1B854] text-[0.625rem] font-[400] bg-[#423A1A40] rounded-[6px] px-[.4rem] py-[.15rem]">Toxicity</div>
              <div className="text-[#D1B854] text-[0.625rem] font-[400] bg-[#423A1A40] rounded-[6px] px-[.4rem] py-[.15rem]">Finance</div>
            </div>
          </div>
          <div className="flex justify-between items-center w-[48%] mb-[1.4rem] px-[1.4rem]">
            <div className="flex justify-start items-center  min-w-[82%]">
              <div className="h-[.75rem] flex justify-start items-start">
                <div className="mr-[0rem] w-[0.75rem] flex justify-start items-start">
                  <Image
                    preview={false}
                    src="/images/drawer/cluster.png"
                    alt="info"
                    style={{ height: '.75rem' }}
                  />
                </div>
              </div>
              <Text_12_400_B3B3B3 className="ml-[.4rem] mr-[.4rem] text-nowrap">
                Cluster Name
              </Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE className="min-w-[3.5rem]">name123</Text_12_400_EEEEEE>
          </div>
        </BudDrawerLayout>
        <ProprietaryCredentialsFormList
          providerType={providerType}
        />
      </BudWraperBox>
    </BudForm>
  );
}
