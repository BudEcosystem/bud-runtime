import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form, Image, Radio } from "antd";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { axiosInstance } from "src/pages/api/requests";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import TextInput from "../components/TextInput";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useProjects } from "src/hooks/useProjects";

export default function AddBenchmark() {
  const { getProjectTags, projectTags } = useProjects();
  const { createBenchmark, setEvalWith, evalWith, stepOneData } =
    usePerfomanceBenchmark();
  const [concurrentRequests, setConcurrentRequests] = useState(
    stepOneData?.concurrent_requests || "",
  );
  const { openDrawerWithStep, openDrawer, step, drawerProps } = useDrawer();
  const { form, submittable } = useContext(BudFormContext);
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
    setEvalWith(stepOneData?.eval_with);
  }, [stepOneData?.eval_with]);

  useEffect(() => {
    console.log("drawerProps", drawerProps?.source);
  }, [drawerProps]);

  return (
    <BudForm
      data={{
        name: stepOneData?.name || "",
        description: stepOneData?.description || "",
        tags: stepOneData?.tags || [],
        concurrent_requests: stepOneData?.concurrent_requests || "",
        eval_with: stepOneData?.eval_with || "",
      }}
      disableNext={!submittable || !evalWith?.length}
      showBack={drawerProps?.source == "modelDetails" ? true : false}
      onBack={() => {
        if (drawerProps?.source == "modelDetails") {
          openDrawer("view-model");
        }
      }}
      onNext={async (values) => {
        if (!submittable || !evalWith.length) {
          form.submit();
          return;
        }
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
              value={stepOneData?.name}
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
              value={stepOneData?.description}
              formItemClassnames="mt-[1.1rem] mb-[1.1rem]"
              info="This is the project’s elevator pitch, use clear and concise words to summarize the project in few sentences"
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
              value={concurrentRequests} // 🔹 use value instead of defaultValue
              onChange={(value) => setConcurrentRequests(value)} // 🔹 this updates the value after filtering
              placeholder="Enter Value"
              rules={[
                { required: true, message: "Please enter concurrent request" },
                // pattern is optional now since we restrict non-numbers via code
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
    </BudForm>
  );
}
