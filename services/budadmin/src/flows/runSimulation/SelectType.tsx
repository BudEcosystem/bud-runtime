
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect } from "react";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import { Image, Checkbox } from 'antd'

import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { Text_10_400_B3B3B3, Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import Tags from "../components/DrawerTags";
import { color } from "echarts";

const evaluationTypes=[
  {
    id: 1,
    icon: '/images/drawer/compare.png',
    title: 'Compare Hardwares',
    tag: {
      name: 'Rule based',
      color: '#D1B854'
    },
    description: 'Compare hardware performance for a specific model and use case.'
  },
  {
    id: 2,
    icon: '/images/drawer/cusecase.png',
    title: 'Compare Usecases',
    tag: {
      name: 'Rule based',
      color: '#D1B854'
    },
    description: 'Compare use case performance on specific model and hardware.'
  },
  {
    id: 3,
    icon: '/images/drawer/cmodel.png',
    title: 'Compare Models',
    tag: {
      name: 'Rule based',
      color: '#D1B854'
    },
    description: 'Compare model performance on specific hardware and use case.'
  },
  {
    id: 4,
    icon: '/images/drawer/memory.png',
    title: 'Estimate Memory Requirements',
    tag: {
      name: 'Rule based',
      color: '#D1B854'
    },
    description: 'Estimate memory requirements for your GenAI deployment'
  },
  {
    id: 5,
    icon: '/images/drawer/roi.png',
    title: 'ROI based Simulation',
    tag: {
      name: 'Rule based',
      color: '#D1B854'
    },
    description: 'Estimate the ROI for your GenAI deployments'
  }
]

type cardProps = {
  data?: any;
  ClassNames?: string;
  selected?: boolean;
  handleClick?: () => void;
};

function CardWithCheckBox({
  data,
  ClassNames,
  selected,
  handleClick,
}: cardProps) {
  const [hover, setHover] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className={`py-[1.34rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box ${ClassNames}`}
    >
      <div className="mr-[1rem] flex flex-col justify-center">
        <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[8px] flex justify-center items-center grow-0 shrink-0">
          <Image
            preview={false}
            src={data.icon}
            className="!w-[1.75rem] !h-[1.75rem]"
            style={{ width: "1.75rem", height: "1.75rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex-auto max-w-[91%]">
        <div className="flex items-center justify-between h-4 max-w-[100%]">
          <div className="flex justify-start items-start gap-[.6rem]">
            <Text_14_400_EEEEEE className="">{data.title}</Text_14_400_EEEEEE>
            <Tags
              name={data.tag.name}
              color={data.tag.color}
            />
          </div>
          <div className="w-[0.875rem] h-[0.875rem]">
            <Checkbox
              style={{
                display: hover || selected ? "flex" : "none",
              }}
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        </div>
        <Text_12_400_757575 className="overflow-hidden truncate pt-[.7rem] max-w-[95%]">
          {data.description}
        </Text_12_400_757575>
      </div>
    </div>
  );
}

export default function SelectEvaluationType() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);
  const { getProviders, providers } = useCloudProviders();
  const [search, setSearch] = React.useState("");
  const { openDrawerWithStep } = useDrawer();
  const { currentWorkflow, updateProvider } = useDeployModel();

  useEffect(() => {
    getProviders(page, limit, search);
  }, []);

  const filteredProviders = providers?.filter((provider) => provider.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <BudForm
      data={{
      }}
      
      // disableNext={!selectedProvider?.id}
      onNext={async () => {
        // if (!currentWorkflow) {
        //   return openDrawerWithStep("select-use-case");
        // } else {
        //   await updateProvider();
        // }
        openDrawerWithStep("select-use-case");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="What simulation would you like to run?"
            description="Select the type of evaluation you want to run."
          />
          <div className="pt-[1.8rem]">
            {evaluationTypes?.map((item, index) => (
              <CardWithCheckBox
                key={index}
                data={item}
                handleClick={() => {
                  // setSelectedProvider(item);
                }}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
