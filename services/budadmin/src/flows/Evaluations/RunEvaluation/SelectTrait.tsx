import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Checkbox } from "antd";
import React, { useEffect } from "react";
import CustomPopover from "src/flows/components/customPopover";
import { useDrawer } from "src/hooks/useDrawer";


export default function SelectTrait() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const { openDrawerWithStep } = useDrawer();
  const [hover, setHover] = React.useState(false);

  const [traits, setTraits] = React.useState([]);
  const traitsList = [
    {
      name: "Trait 1",
      description: "Description for Trait 1",
      selected: false,
      is_present_in_model: false
    },
    {
      name: "Trait 2",
      description: "Description for Trait 2",
      selected: false,
      is_present_in_model: false
    },
    // Add more traits as needed
  ];

  const triatCard = (data) => {
    const {
      name,
      description,
      selected = false,
      hideSelect = false
    } = data;
    return (
      <div
        onMouseEnter={() => setHover(true)}
        onClick={null}
        onMouseLeave={() => setHover(false)}
        className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] ${data.is_present_in_model ? 'opacity-30 !cursor-not-allowed' : ''}`}
      >

        <div className="flex justify-between flex-col w-full max-w-[85%]">
          <div className="flex items-center justify-between ">
            <div className="flex flex-grow max-w-[90%]"

            >
              <CustomPopover title={name}>
                <div className="text-[#EEEEEE] mr-2 pb-[.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap"
                >
                  {name}
                </div>
              </CustomPopover>
            </div>
            <div
              style={{
                // Hidden temprorily
                display: (hover || selected) && !hideSelect ? "flex" : "none",
                // display: "none",
              }}
              className="justify-end items-center]"
            >
              <CustomPopover
                Placement="topRight"
                title={data.is_present_in_model ? "Already added to model repository" : "Add to model repository"}
              >
                <Checkbox
                  checked={selected} className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center" />
              </CustomPopover>
            </div>
          </div>
          <CustomPopover title={description}>
            <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs line-clamp-2 leading-[150%]">
              {description || "-"}
            </div>
          </CustomPopover>

        </div>
      </div>
    );
  };

  useEffect(() => {

  }, [page]);


  return (
    <BudForm
      data={{}}
      // disableNext={!selectedModel?.id}
      // onNext={async () => {
      //   openDrawerWithStep("Benchmark-Configuration");
      // }}
      onBack={async () => {
        openDrawerWithStep("select-model-new-evaluation");
      }
      }
      backText="Back"
      onNext={() => {

        openDrawerWithStep("select-evaluation");
      }}
      nextText="Next"
    >

      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Trait"
            description="Select the trait from the list"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <div className="px-[1.4rem] pb-[.875rem] pt-[1.25rem] flex justify-between items-center">
            <div className="text-[#757575] text-[.75rem] font-[400]">
              Traits Available <span className="text-[#EEEEEE]">{traitsList?.length}</span>
            </div>
          </div>

          {traitsList.map((trait, index) => (
            <div key={index}>
              {triatCard(trait)}
            </div>
          ))}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
