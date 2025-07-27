
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useProjects } from "src/hooks/useProjects";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { axiosInstance } from "src/pages/api/requests";
import TextInput from "../components/TextInput";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export default function Configuration() {
  const { currentWorkflow, stepTwo, stepTwoData } = usePerfomanceBenchmark();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
  const [options, setOptions] = useState([]);
  const [evalWith, setEvalWith] = useState('Dataset');

  async function fetchList(tagname) {
    await axiosInstance("/projects/tags?page=1&limit=1000").then((result) => {
      const data = result.data?.results?.map((result) => ({
        ...result,
        name: result.name,
        color: result.color,
      }));
      setOptions(data);
    });
  }

  useEffect(() => {
    fetchList("");
  }, []);

  return (
    <BudForm
      data={{
        max_input_tokens: stepTwoData?.max_input_tokens || "",
        max_output_tokens: stepTwoData?.max_output_tokens || "",
      }}
      disableNext={!submittable}
      onNext={async(values) => {
        if (!submittable) {
          form.submit();
          return;
        };
        stepTwo(values)
          .then((result) => {
            if (result) {
              openDrawerWithStep("Select-Cluster");
            }
          })
      }}
      backText="Back"
      onBack={() => {
        openDrawerWithStep("model_benchmark");
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Configuration"
            description="Enter the configuration's for the benchmark"
          />
          <DrawerCard classNames="pb-0">
            <TextInput
              name="max_input_tokens"
              label="Max Input Tokens"
              onChange={(value) => null}
              placeholder="Enter number of tokens"
              rules={[{ required: true, message: "Enter number of tokens" }]}
              ClassNames="mt-[.3rem]"
              formItemClassnames="pb-[.6rem] mb-[1rem]"
              infoText="Enter number of tokens"
              InputClasses="py-[.5rem]"
            />

            <TextInput
              name="max_output_tokens"
              label="Max Output Tokens"
              onChange={(value) => null}
              placeholder="Enter number of tokens"
              rules={[{ required: true, message: "Enter number of tokens" }]}
              ClassNames="mt-[.55rem]"
              formItemClassnames="pb-[.6rem] mb-[.6rem]"
              infoText="Enter number of tokens"
              InputClasses="py-[.5rem]"
            />

          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
