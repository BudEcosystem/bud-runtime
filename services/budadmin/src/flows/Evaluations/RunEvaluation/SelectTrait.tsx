import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Checkbox } from "antd";
import React, { useEffect, useState } from "react";
import CustomPopover from "src/flows/components/customPopover";
import { useDrawer } from "src/hooks/useDrawer";
import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast, errorToast } from "@/components/toast";

export default function SelectTrait() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const { openDrawerWithStep, drawerProps } = useDrawer();
  const [hover, setHover] = React.useState(false);
  const { createWorkflow, currentWorkflow, getTraits, traitsList } =
    useEvaluations();

  const [selectedTraits, setSelectedTraits] = useState<string[]>([]);

  const handleTraitToggle = (traitId: string) => {
    setSelectedTraits((prev) => {
      if (prev.includes(traitId)) {
        return prev.filter((id) => id !== traitId);
      } else {
        return [...prev, traitId];
      }
    });
  };

  const triatCard = (data) => {
    const { id, name, description, hideSelect = false } = data;
    const selected = selectedTraits.includes(id);

    return (
      <div
        onMouseEnter={() => setHover(true)}
        onClick={() => !data.is_present_in_model && handleTraitToggle(id)}
        onMouseLeave={() => setHover(false)}
        className={`w-full pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] ${data.is_present_in_model ? "opacity-30 !cursor-not-allowed" : ""}`}
      >
        <div className="flex justify-between flex-col w-full ">
          <div className="flex items-center justify-between ">
            <div className="flex flex-grow max-w-[90%]">
              <CustomPopover title={name}>
                <div className="text-[#EEEEEE] mr-2 pb-[.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
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
                title={
                  data.is_present_in_model
                    ? "Already added to model repository"
                    : "Add to model repository"
                }
              >
                <Checkbox
                  checked={selected}
                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                />
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
    // Fetch traits when component mounts
    getTraits({ page, limit });
  }, [page]);

  useEffect(()=> {
    setSelectedTraits(Array.isArray(currentWorkflow?.workflow_steps?.trait_ids) ? currentWorkflow?.workflow_steps?.trait_ids : [])
  }, [currentWorkflow])

  return (
    <BudForm
      data={{}}
      disableNext={selectedTraits.length === 0}
      onBack={async () => {
        openDrawerWithStep("select-model-new-evaluation");
      }}
      backText="Back"
      onNext={async () => {
        try {
          // Check if we have selected traits
          if (selectedTraits.length === 0) {
            errorToast("Please select at least one trait");
            return;
          }

          if (!currentWorkflow?.workflow_id) {
            errorToast("Workflow not found. Please start over.");
            return;
          }

          // Get experiment ID from workflow or drawer props
          const experimentId =
            currentWorkflow?.workflow_steps?.experiment_id|| drawerProps?.experimentId;

          if (!experimentId) {
            errorToast("Experiment ID not found");
            return;
          }

          // Prepare payload for step 3
          const payload = {
            workflow_id: currentWorkflow.workflow_id,
            step_number: 3,
            workflow_total_steps: 5,
            trigger_workflow: false,
            stage_data: {
              trait_ids: selectedTraits,
            },
          };

          // Call the API
          const response = await createWorkflow(
            experimentId,
            payload,
          );

          // Navigate to next step
          openDrawerWithStep("select-evaluation");
        } catch (error) {
          console.error("Failed to update evaluation workflow:", error);
          errorToast("Failed to select traits");
        }
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
              Traits Available{" "}
              <span className="text-[#EEEEEE]">{traitsList?.length || 0}</span>
            </div>
          </div>

          {traitsList && traitsList.length > 0 ? (
            traitsList.map((trait) => (
              <div key={trait.id}>{triatCard(trait)}</div>
            ))
          ) : (
            <div className="px-[1.4rem] py-[2rem] text-center text-[#757575]">
              Loading traits...
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
