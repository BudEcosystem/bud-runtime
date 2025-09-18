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
    icon: "/images/drawer/intelimg.png",
    title: "Hardware Name",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    website:
      "https://www.intel.com/content/www/us/en/events/on-event-series/vision.html",
  },
  {
    id: 2,
    icon: "/images/drawer/nvdia.png",
    title: "Summarization",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    website:
      "https://www.intel.com/content/www/us/en/events/on-event-series/vision.html",
  },
  {
    id: 3,
    icon: "/images/drawer/zephyr.png",
    title: "Chat",
    description:
      "Need to add hardware description here, to add hardware descrip...",
    website:
      "https://www.intel.com/content/www/us/en/events/on-event-series/vision.html",
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
      className={`py-[.85rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex items-start border-box ${ClassNames}`}
    >
      <div className="mr-[1rem] flex flex-col justify-center">
        <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[.52rem] flex justify-center items-center grow-0 shrink-0">
          <Image
            preview={false}
            src={data.icon}
            style={{ width: "1.67969rem", height: "1.67969rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex-auto max-w-[91%]">
        <div className="flex items-center justify-between max-w-[100%]">
          <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
            <Text_14_400_EEEEEE className="leading-[100%]">
              {data.title}
            </Text_14_400_EEEEEE>
            <Tags
              name="Website Link"
              color="#965CDE"
              classNames="pt-[.1rem] pb-[0]"
              onTagClick={() => {
                window.open(data.website, "_blank");
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
        <Text_10_400_B3B3B3 className="overflow-hidden truncate max-w-[95%]">
          {data.description}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default function SelectHardware() {
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
        openDrawerWithStep("model-quantisation");
      }}
      onNext={async () => {
        openDrawerWithStep("hardware-pecifications");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={`Select Hardware`}
            description={`Select the hardware from the list`}
          />
          <div>
            <div className="px-[1.4rem] py-[1.8rem] rounded-es-lg rounded-ee-lg pb-[.5rem]">
              <div className="flex items-center justify-between gap-[0.8rem]">
                <SearchHeaderInput
                  placeholder="Hardware names, Tags"
                  searchValue={search}
                  expanded
                  setSearchValue={setSearch}
                  classNames="border border-[.5px] border-[#757575]"
                />
                {/* <PrimaryButton classNames="!min-w-[120px] !px-[2.6rem]"
                  onClick={null}
                  text={'+ Add a custom use case'}
                >
                </PrimaryButton> */}
              </div>
            </div>

            <div className="flex justify-between align-cneter px-[1.4rem] pb-[.7rem] mt-6">
              <div className="text-[#757575] text-[.75rem] font-[400]">
                Use Cases Available <span className="text-[#EEEEEE]">15</span>
              </div>
              {/* <div className="flex justify-end align-center gap-[.6rem]">
                <Text_12_600_EEEEEE>Select All</Text_12_600_EEEEEE>
                <Checkbox
                  checked={false}
                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                  onChange={null}
                />
              </div> */}
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
