import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Input } from 'antd';
import { SearchOutlined } from "@ant-design/icons";
import { Text_12_400_757575, Text_12_600_EEEEEE } from "@/components/ui/text";
import EvaluationList, { Evaluation } from "src/flows/components/AvailableEvaluations";
import BudStepAlert from "src/flows/components/BudStepAlert";
export default function SelectEvaluation() {
  // Mock evaluation data - replace with actual API call
  const mockEvaluations: Evaluation[] = [
    {
      id: "eval-1",
      name: "Truthfulness Evaluation",
      description: "Evaluates the model's ability to provide accurate and truthful responses",
      category: "accuracy",
      tags: ["accuracy", "truthfulness", "hallucination"]
    },
    {
      id: "eval-2",
      name: "Code Generation Benchmark",
      description: "Tests the model's ability to generate syntactically correct and functional code",
      category: "code",
      tags: ["code", "programming", "syntax"]
    },
    {
      id: "eval-3",
      name: "Language Understanding",
      description: "Comprehensive evaluation of natural language understanding capabilities",
      category: "language",
      tags: ["NLU", "comprehension", "context"]
    },
    {
      id: "eval-4",
      name: "Mathematical Reasoning",
      description: "Assesses mathematical problem-solving and logical reasoning abilities",
      category: "math",
      tags: ["math", "logic", "reasoning"]
    },
    {
      id: "eval-5",
      name: "Safety & Ethics",
      description: "Evaluates adherence to safety guidelines and ethical considerations",
      category: "safety",
      tags: ["safety", "ethics", "harmful content"]
    }
  ];
  const [search, setSearch] = React.useState("");
  const [selectedEvaluation, setSelectedEvaluation] = React.useState<Evaluation | null>(null);
  const { openDrawerWithStep } = useDrawer();
  
  const filteredEvaluations = mockEvaluations.filter((evaluation) => 
    evaluation.name.toLowerCase().includes(search.toLowerCase()) || 
    evaluation.description?.toLowerCase().includes(search.toLowerCase()) ||
    evaluation.tags?.some(tag => tag.toLowerCase().includes(search.toLowerCase()))
  );



  return (
    <BudForm
      data={{}}
      // disableNext={!selectedModel?.id}
      // onNext={async () => {
      //   openDrawerWithStep("Benchmark-Configuration");
      // }}
      onBack={async () => {
        openDrawerWithStep("select-traits");
      }
      }
      backText="Back"
      onNext={() => {
        openDrawerWithStep("evaluation-summary");
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
                  prefix={<SearchOutlined style={{ color: '#757575', marginRight: 8 }} />}
                  style={{
                    backgroundColor: 'transparent',
                    color: '#EEEEEE', // Text color
                  }}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="custom-search bg-transparent text-[#EEEEEE] font-[400] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full"
                />
              </div>
              <div className="flex justify-start items-center mt-[1.45rem]">
                <Text_12_400_757575 className="mr-[.3rem] ">Evaluations Available&nbsp;</Text_12_400_757575>
                <Text_12_600_EEEEEE>{filteredEvaluations.length}</Text_12_600_EEEEEE>
              </div>
            </div>
            <div className="evaluationCardWrap w-full ">
              <div className="evaluationCard w-full mt-[0rem]">
                {filteredEvaluations.length > 0 ?
                  <EvaluationList
                    evaluations={filteredEvaluations}
                    handleEvaluationSelection={(evaluation) => {
                      setSelectedEvaluation(evaluation);
                    }}
                    selectedEvaluation={selectedEvaluation} />
                  : (
                    <>
                      <div
                        className="mt-[1.5rem]"
                      />
                      <BudStepAlert
                        type="warining"
                        title='No Evaluations Found'
                        description='No evaluations match your search criteria. Try adjusting your search terms.'
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
