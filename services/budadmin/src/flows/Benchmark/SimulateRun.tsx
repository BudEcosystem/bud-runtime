import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { PrimaryButton, SecondaryButton } from "@/components/ui/bud/form/Buttons";
import { Text_12_400_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";


export default function StimulateRun() {
  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } = useDrawer();
  const { currentWorkflow, setRunAsSimulation, runAsSimulation, stepEight } = usePerfomanceBenchmark();

  return (
    <BudForm
      data={{}}
      onBack={async () => {
        openDrawerWithStep("Benchmark-Configuration");
      }
      }
      nextText=""

    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Benchmark Configuration"
            description="With Bud Simulator you can simulate the performance of a model on selected
hardware configuration. We have usually noticed less than 8% accuracy difference between an actual benchmark, but with almost zero cost."
            classNames="pt-[.8rem] pb-[1rem]"
            descriptionClass="pt-[.35rem]"
            descriptionTextClass="leading-[1.13rem]"
          />
          <div className="px-[1.4rem] mt-[.9rem] mb-[1.55rem]">
            <div>
              <Text_14_400_EEEEEE>A Good Rule of thumb that we recommend:</Text_14_400_EEEEEE>
            </div>
            <div className="pt-[1.05rem] flex flex-col gap-y-[.6rem]">
              <div className="flex items-baseline justify-start gap-x-[.7rem]">
                <div className="bg-[#965CDE] w-[0.5rem] h-[0.5rem] rounded-full"></div>
                <div className="w-[95%]">
                  <Text_12_400_EEEEEE>For production deployments, always simulate & do actual benchmarking on the hardware.</Text_12_400_EEEEEE>
                </div>
              </div>
              <div className="flex items-center justify-start gap-x-[.7rem]">
                <div className="bg-[#965CDE] w-[0.5rem] h-[0.5rem] rounded-full"></div>
                <div>
                  <Text_12_400_EEEEEE>For test, staging or dev clusters, mostly simulation will suffice.</Text_12_400_EEEEEE>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-x-[.65rem] mt-[1.25rem] mr-[.1rem]">
              <SecondaryButton
                onClick={() => {
                  setRunAsSimulation(true)
                  stepEight()
                    .then((result) => {
                      if (result) {
                        openDrawerWithStep("Benchmarking-Progress")
                      }
                    })
                  
                }}
                classNames="px-[.6rem]"
                text="Simulate"
              ></SecondaryButton>
              <PrimaryButton
                type="submit"
                onClick={() => {
                  setRunAsSimulation(false)
                  stepEight()
                    .then((result) => {
                      if (result) {
                        openDrawerWithStep("Benchmarking-Progress")
                      }
                    })
                }}
                classNames=""
                text="Run on Cluster"
              ></PrimaryButton>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
