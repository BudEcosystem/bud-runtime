import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Checkbox, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { Text_12_400_757575, Text_12_600_EEEEEE } from "@/components/ui/text";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useEvaluations } from "src/hooks/useEvaluations";
import { successToast, errorToast } from "@/components/toast";
import { ChevronRight } from "lucide-react";
import CustomPopover from "src/flows/components/customPopover";
export default function SelectEvaluation() {
  const [search, setSearch] = React.useState("");
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const {
    openDrawerWithStep,
    drawerProps,
    openDrawerWithExpandedStep,
    expandedStep,
  } = useDrawer();
  const {
    createWorkflow,
    currentWorkflow,
    getEvaluations,
    evaluationsList,
    setSelectedEvals,
    selectedEvals,
    getEvaluationDetails,
  } = useEvaluations();
  const [hover, setHover] = React.useState(false);

  useEffect(() => {


    const traitIds =
      currentWorkflow?.workflow_steps?.stage_data?.trait_ids ||
      currentWorkflow?.workflow_steps?.trait_ids ||
      [];


    // Fetch evaluations/datasets filtered by selected traits
    getEvaluations({
      page: 1,
      limit: 100,
      trait_ids: traitIds,
    });
  }, [currentWorkflow, getEvaluations]);

  const handleDatasetToggle = (datasetId: string) => {
    setSelectedDatasets((prev) => {
      if (prev.includes(datasetId)) {
        return prev.filter((id) => id !== datasetId);
      } else {
        return [...prev, datasetId];
      }
    });
  };

  // Map evaluations to the expected format
  const evaluationsAsDatasets =
    evaluationsList?.map((evaluation) => ({
      id: evaluation.id,
      name: evaluation.name,
      description: evaluation.description,
      category: evaluation.task_type?.[0] || "general",
      tags: evaluation.domains || [],
    })) || [];

  const filteredEvaluations = evaluationsAsDatasets.filter(
    (evaluation) =>
      evaluation.name.toLowerCase().includes(search.toLowerCase()) ||
      evaluation.description?.toLowerCase().includes(search.toLowerCase()) ||
      evaluation.tags?.some((tag) =>
        tag.toLowerCase().includes(search.toLowerCase()),
      ),
  );

  useEffect(()=> {
    setSelectedDatasets(Array.isArray(currentWorkflow?.workflow_steps?.dataset_ids) ? currentWorkflow?.workflow_steps?.dataset_ids : [])
  }, [currentWorkflow])
  return (
    <BudForm
      data={{}}
      disableNext={selectedDatasets.length === 0}
      onBack={async () => {
        openDrawerWithStep("select-traits");
      }}
      backText="Back"
      onNext={async () => {
        try {
          // Check if we have selected datasets
          if (selectedDatasets.length === 0) {
            errorToast("Please select at least one evaluation dataset");
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

          // Prepare payload for step 4
          const payload = {
            workflow_id: currentWorkflow.workflow_id,
            step_number: 4,
            workflow_total_steps: 5,
            trigger_workflow: false,
            stage_data: {
              dataset_ids: selectedDatasets,
            },
          };

          // Call the API
          const response = await createWorkflow(
            experimentId,
            payload,
          );

          // Navigate to next step
          openDrawerWithStep("evaluation-summary");
        } catch (error) {
          console.error("Failed to update evaluation workflow:", error);
          errorToast("Failed to select evaluation datasets");
        }
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Evaluation"
            description="Select model evaluations to verify the performance benchmarks. This will help you understand the strengths and the weakness of the model"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <div className="flex flex-col	justify-start items-center w-full">
            {/* <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Select Cluster</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.7rem]">Description</Text_12_400_757575>
            </div> */}
            <div className="p-[1.35rem] pt-[1.05rem] pb-[.7rem] w-full">
              <div className="w-full">
                <Input
                  placeholder="Search"
                  prefix={
                    <SearchOutlined
                      style={{ color: "#757575", marginRight: 8 }}
                    />
                  }
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE", // Text color
                  }}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="custom-search bg-transparent text-[#EEEEEE] font-[400] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full"
                />
              </div>
              <div className="flex justify-start items-center mt-[1.45rem]">
                <Text_12_400_757575 className="mr-[.3rem] ">
                  Evaluations Available&nbsp;
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>
                  {filteredEvaluations.length}
                </Text_12_600_EEEEEE>
              </div>
            </div>
            <div className="evaluationCardWrap w-full ">
              <div className="evaluationCard w-full mt-[0rem]">
                {filteredEvaluations.length > 0 ? (
                  <div className="space-y-0">
                    {filteredEvaluations.map((evaluation) => (
                      <div
                        onMouseEnter={() => setHover(true)}
                        key={evaluation.id}
                        onClick={() => {
                          handleDatasetToggle(evaluation.id);
                          setSelectedEvals([evaluation]); // Set the selected evaluation as array
                        }}
                        className={`p-4 border-b border-[#1F1F1F] cursor-pointer hover:bg-[#FFFFFF08] transition-colors ${
                          selectedDatasets.includes(evaluation.id)
                            ? "bg-[#FFFFFF10]"
                            : ""
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center justify-between ">
                              <div
                                className="flex flex-grow max-w-[90%]"
                                style={{
                                  width:
                                    hover || selectedEvals ? "12rem" : "90%",
                                }}
                              >
                                <CustomPopover title={evaluation.name}>
                                  <div className="text-[#EEEEEE] mr-2 pb-[.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
                                    {evaluation.name}
                                  </div>
                                </CustomPopover>
                              </div>
                              <div
                                style={{
                                  // Hidden temprorily
                                  display:
                                    hover || selectedEvals ? "flex" : "none",
                                  // display: "none",
                                }}
                                className="justify-end items-center]"
                              >
                                <div
                                  className={`items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex mr-[.6rem] whitespace-nowrap }`}
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (expandedStep) return;

                                    // Set the selected evaluation and fetch its details
                                    setSelectedEvals([evaluation]);

                                    try {
                                      // Fetch evaluation details before opening the drawer
                                      await getEvaluationDetails(evaluation.id);
                                      // Open the expanded drawer to show details
                                      openDrawerWithExpandedStep(
                                        "eval-details",
                                      );
                                    } catch (error) {
                                      console.error(
                                        "Failed to fetch evaluation details:",
                                        error,
                                      );
                                      errorToast(
                                        "Failed to load evaluation details",
                                      );
                                    }
                                  }}
                                >
                                  See More <ChevronRight className="h-[1rem]" />
                                </div>

                                <Checkbox
                                  checked={selectedDatasets.includes(
                                    evaluation.id,
                                  )}
                                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                                />
                              </div>
                            </div>
                            <Text_12_400_757575 className="line-clamp-2">
                              {evaluation.description}
                            </Text_12_400_757575>
                            {evaluation.tags && evaluation.tags.length > 0 && (
                              <div className="flex gap-2 mt-2">
                                {evaluation.tags.slice(0, 3).map((tag, idx) => (
                                  <span
                                    key={idx}
                                    className="text-[10px] px-2 py-1 bg-[#1F1F1F] rounded text-[#757575]"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="mt-[1.5rem]" />
                    <BudStepAlert
                      type="warining"
                      title="No Evaluations Found"
                      description="No evaluations match your search criteria. Try adjusting your search terms."
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
