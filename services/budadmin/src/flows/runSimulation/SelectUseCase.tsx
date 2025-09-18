import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import React, { useContext, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useDeployModel } from "src/stores/useDeployModel";
import { Image, Checkbox } from "antd";
import {
  Text_10_400_B3B3B3,
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import Tags from "../components/DrawerTags";
import SearchHeaderInput from "../components/SearchHeaderInput";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

const useCases = [
  {
    id: 1,
    icon: "/images/drawer/question.png",
    title: "Question Answering",
    description:
      "Here we can add why or when the user should choose this template",
  },
  {
    id: 2,
    icon: "/images/drawer/summary.png",
    title: "Summarization",
    description:
      "Here we can add why or when the user should choose this template",
  },
  {
    id: 3,
    icon: "/images/drawer/chatIcon.png",
    title: "Chat",
    description: "parallel beams: 5, input tokens : 500, output tokens: 1000",
  },
  {
    id: 4,
    icon: "/images/drawer/chatIcon.png",
    title: "Chat",
    description: "parallel beams: 5, input tokens : 500, output tokens: 1000",
  },

  {
    id: 5,
    icon: "/images/drawer/code.png",
    title: "Code Gen",
    description:
      "Here we can add why or when the user should choose this template",
  },
];

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
      className={`py-[.85rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box ${ClassNames}`}
    >
      <div className="mr-[.8rem] flex flex-col justify-center">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[8px] flex justify-center items-center grow-0 shrink-0">
          <Image
            preview={false}
            src={data.icon}
            className="!w-[1.25rem] !h-[1.25rem]"
            style={{ width: "1.25rem", height: "1.25rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex-auto max-w-[91%]">
        <div className="flex items-center justify-between h-4 max-w-[100%]">
          <div className="flex justify-start items-start gap-[.6rem]">
            <Text_14_400_EEEEEE className="">{data.title}</Text_14_400_EEEEEE>
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
        <Text_10_400_B3B3B3 className="overflow-hidden truncate pt-[.2rem] max-w-[95%]">
          {data.description}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default function SelectUseCase() {
  const { openDrawerWithStep } = useDrawer();

  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(100);

  const { selectedProvider } = useDeployModel();
  const [models, setModels] = React.useState([]);
  const { isExpandedViewOpen } = useContext(BudFormContext);

  const { loading, fetchModels } = useModels();

  const [search, setSearch] = React.useState("");
  const [showAllTags, setShowAllTags] = React.useState(false);
  const { selectedModel, setSelectedModel, currentWorkflow, updateCloudModel } =
    useDeployModel();

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      setSelectedModel(currentWorkflow.workflow_steps.model);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    fetchModels({
      page,
      limit,
      table_source: "cloud_model",
      source: selectedProvider?.type,
    }).then((data) => {
      setModels(data);
    });
  }, []);

  const filteredModels = models?.filter((model) => {
    return (
      model.name?.toLowerCase().includes(search.toLowerCase()) ||
      model.tags?.some((task) =>
        task.name?.toLowerCase().includes(search.toLowerCase()),
      ) ||
      `${model.model_size}`.includes(search.toLowerCase())
    );
  });

  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("select-evaluation-type");
      }}
      onNext={async () => {
        openDrawerWithStep("additional-settingse");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={`Select Use Cases`}
            description={`Select the use cases you want to evaluate for a specific model and hardware.`}
          />
          <div>
            <div className="px-[1.4rem] py-[1.8rem] rounded-es-lg rounded-ee-lg pb-[.5rem]">
              <div className="flex items-center justify-between gap-[0.8rem]">
                <SearchHeaderInput
                  placeholder="Search use cases"
                  searchValue={search}
                  expanded
                  setSearchValue={setSearch}
                  classNames="border border-[.5px] border-[#757575]"
                />
                <PrimaryButton
                  classNames="!min-w-[120px] !px-[2.6rem]"
                  onClick={null}
                  text={"+ Add a custom use case"}
                ></PrimaryButton>
              </div>
            </div>

            <div className="flex justify-between align-cneter px-[1.4rem] pb-[.7rem] mt-6">
              <div className="text-[#757575] text-[.75rem] font-[400]">
                Use Cases Available <span className="text-[#EEEEEE]">15</span>
              </div>
              <div className="flex justify-end align-center gap-[.6rem]">
                <Text_12_600_EEEEEE>Select All</Text_12_600_EEEEEE>
                <Checkbox
                  checked={false}
                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                  onChange={null}
                />
              </div>
            </div>
            <div className="">
              {useCases?.length > 0 ? (
                <>
                  {useCases?.map((model, index) => (
                    <CardWithCheckBox
                      key={index}
                      data={model}
                      handleClick={() => {}}
                    />
                  ))}
                </>
              ) : (
                <div className="flex justify-center items-center min-h-[4rem]">
                  <Text_12_300_EEEEEE>
                    To add new models for the provider, click the &quot;+Cloud
                    Model&quot; button
                  </Text_12_300_EEEEEE>
                </div>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
