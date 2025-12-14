import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form, Radio } from "antd";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import TextInput from "../components/TextInput";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useProjects } from "src/hooks/useProjects";

// Inner component that can access BudFormContext
function AddBenchmarkFormContent({
  stepOneData,
  evalWith,
  setEvalWith,
  options,
  concurrentRequests,
  setConcurrentRequests,
}: {
  stepOneData: any;
  evalWith: string;
  setEvalWith: (val: string) => void;
  options: any[];
  concurrentRequests: string;
  setConcurrentRequests: (val: string) => void;
}) {
  const { form } = useContext(BudFormContext);

  // Update form fields when stepOneData changes (e.g., when opening from task island or navigating back)
  useEffect(() => {
    if (stepOneData && form) {
      form.setFieldsValue({
        name: stepOneData.name || "",
        description: stepOneData.description || "",
        tags: stepOneData.tags || [],
        concurrent_requests: stepOneData.concurrent_requests || "",
        eval_with: stepOneData.eval_with || "",
      });
      if (stepOneData.concurrent_requests) {
        setConcurrentRequests(String(stepOneData.concurrent_requests));
      }
      if (stepOneData.eval_with) {
        setEvalWith(stepOneData.eval_with);
      }
    }
  }, [stepOneData, form]);

  return (
    <BudWraperBox>
      <BudDrawerLayout>
        <DrawerTitleCard
          title="Create Benchmark"
          description="Enter the additional concurrency to identify the required hardware"
        />
        <DrawerCard classNames="pb-0">
          <TextInput
            name="name"
            label="Benchmark Name"
            onChange={(value) => null}
            placeholder="Enter Name"
            rules={[
              { required: true, message: "Please enter benchmark name" },
            ]}
            ClassNames="mt-[.3rem]"
            formItemClassnames="pb-[.6rem] mb-[1rem]"
            infoText="Enter the benchmark name"
            InputClasses="py-[.5rem]"
            replaceSpacesWithHyphens={true}
          />
          <TagsInput
            label="Tags"
            required
            options={options}
            defaultValue={stepOneData?.tags}
            info="Add keywords to help organize and find your project later."
            name="tags"
            placeholder="Add Tags (e.g. Data Science, Banking) "
            rules={[
              {
                required: true,
                message: "Please add tags to categorize the project.",
              },
            ]}
          />
          <TextAreaInput
            name="description"
            label="Description"
            required
            formItemClassnames="mt-[1.1rem] mb-[1.1rem]"
            info="This is the project's elevator pitch, use clear and concise words to summarize the project in few sentences"
            placeholder="Provide a brief description about the Benchmark."
            rules={[
              {
                required: true,
                message: "Provide a brief description about the Benchmark.",
              },
            ]}
          />
          <TextInput
            name="concurrent_requests"
            label="Concurrent Request"
            value={concurrentRequests}
            onChange={(value) => setConcurrentRequests(value)}
            placeholder="Enter Value"
            rules={[
              { required: true, message: "Please enter concurrent request" },
            ]}
            ClassNames="mt-[.55rem]"
            formItemClassnames="pb-[.6rem] mb-[.6rem]"
            infoText="Enter the concurrent request"
            InputClasses="py-[.5rem]"
            allowOnlyNumbers={true}
          />
          <Form.Item name="eval_with">
            <div className="budRadioGroup">
              <InfoLabel
                required={true}
                text="Eval with"
                classNames="text-nowrap h-auto bg-[transparent]"
                content="Choose Eval with"
              />
              <Radio.Group
                value={evalWith || ""}
                onChange={(e) => setEvalWith(e.target.value)}
                className="rounded-[5px] mt-[.5rem]"
                name="eval_with"
                options={[
                  { value: "dataset", label: "Dataset" },
                  { value: "configuration", label: "Configuration" },
                ]}
              />
            </div>
          </Form.Item>
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}

export default function AddBenchmark() {
  const { getProjectTags, projectTags } = useProjects();
  const { createBenchmark, setEvalWith, evalWith, stepOneData } =
    usePerfomanceBenchmark();
  const [concurrentRequests, setConcurrentRequests] = useState(
    stepOneData?.concurrent_requests ? String(stepOneData.concurrent_requests) : "",
  );
  const { openDrawerWithStep, openDrawer, drawerProps } = useDrawer();
  const [options, setOptions] = useState([]);

  async function fetchList() {
    const data = projectTags?.map((result) => ({
      ...result,
      name: result.name,
      color: result.color,
    }));
    setOptions(data);
  }

  useEffect(() => {
    getProjectTags();
  }, []);

  useEffect(() => {
    fetchList();
  }, [projectTags]);

  useEffect(() => {
    if (stepOneData?.eval_with) {
      setEvalWith(stepOneData.eval_with);
    }
  }, [stepOneData?.eval_with]);

  // Update concurrentRequests when stepOneData changes
  useEffect(() => {
    if (stepOneData?.concurrent_requests) {
      setConcurrentRequests(String(stepOneData.concurrent_requests));
    }
  }, [stepOneData?.concurrent_requests]);

  return (
    <BudForm
      data={{
        name: stepOneData?.name || "",
        description: stepOneData?.description || "",
        tags: stepOneData?.tags || [],
        concurrent_requests: stepOneData?.concurrent_requests ? String(stepOneData.concurrent_requests) : "",
        eval_with: stepOneData?.eval_with || "",
      }}
      disableNext={!evalWith?.length}
      showBack={drawerProps?.source == "modelDetails" ? true : false}
      onBack={() => {
        if (drawerProps?.source == "modelDetails") {
          openDrawer("view-model");
        }
      }}
      onNext={async (values) => {
        createBenchmark(values).then((result) => {
          if (result) {
            if (evalWith == "dataset") {
              openDrawerWithStep("add-Datasets");
            } else if (evalWith == "configuration") {
              openDrawerWithStep("add-Configuration");
            }
          }
        });
      }}
      nextText="Next"
    >
      <AddBenchmarkFormContent
        stepOneData={stepOneData}
        evalWith={evalWith}
        setEvalWith={setEvalWith}
        options={options}
        concurrentRequests={concurrentRequests}
        setConcurrentRequests={setConcurrentRequests}
      />
    </BudForm>
  );
}
