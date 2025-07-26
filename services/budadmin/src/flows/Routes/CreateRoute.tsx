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
import { useRoutes } from "src/hooks/useRoutes";

export default function CreateRoute() {
  const { getProjectTags, projectTags } = useProjects();
  const { setStrategy, strategy, stepOneData, setStepOneData } = useRoutes();
  const { openDrawerWithStep, step } = useDrawer();
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

  // useEffect(() => {
  //   setStrategy(stepOneData?.routing_strategy?.[0]?.name || "");
  // }, [stepOneData?.routing_strategy]);

  return (
    <BudForm
      data={{
        name: stepOneData?.name || "",
        description: stepOneData?.description || "",
        tags: stepOneData?.tags || [],
        strategy: stepOneData?.routing_strategy?.[0]?.name || "" ,
      }}
      disableNext={!submittable}
      onNext={async (values) => {
        console.log("values", values);
        console.log("strategy", strategy);
        if (!submittable) {
          form.submit();
          return;
        }
        setStepOneData({
          ...stepOneData,
          name: values.name,
          description: values.description,
          tags: values.tags,
          routing_strategy: [
            {
              name: values.strategy,
            },
          ],
        });
        openDrawerWithStep("select-endpoints-route");
        // createBenchmark(values).then((result) => {
        //   if (result) {
        //     if (evalWith == "dataset") {
        //       openDrawerWithStep("add-Datasets");
        //     } else if (evalWith == "configuration") {
        //       openDrawerWithStep("add-Configuration");
        //     }
        //   }
        // });
      }}
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Route"
            description="A route allows you to create a custom OpenAI Compatible endpoint, with a swarm of models working together based on pre-set conditions to meet your Accuracy, ROI and performance requirements"
          />
          <DrawerCard classNames="pb-0">
            <TextInput
              name="name"
              label="Route Name"
              onChange={(value) => null}
              placeholder="Enter Route Name"
              rules={[
                { required: true, message: "Please enter route name" },
              ]}
              ClassNames="mt-[.3rem]"
              formItemClassnames="pb-[.6rem] mb-[1rem]"
              infoText="Enter route name"
              InputClasses="py-[.5rem]"
            />
            <TagsInput
              label="Tags"
              options={options}
              defaultValue={stepOneData?.tags}
              info="Add keywords to help organize and find your project later."
              name="tags"
              placeholder="Add Tags (e.g. Data Science, Banking) "
              rules={[
                {
                  required: false,
                  message: "Please add tags to categorize the project.",
                },
              ]}
            />
            <TextAreaInput
              name="description"
              label="Description"
              defaultValue={stepOneData?.description}
              formItemClassnames="mt-[1.1rem] mb-[1.1rem]"
              info="This is the project’s elevator pitch, use clear and concise words to summarize the project in few sentences"
              placeholder="Provide a brief description about the Benchmark."
              rules={[
                {
                  required: false,
                  message: "Provide a brief description about the Benchmark.",
                },
              ]}
            />

            <Form.Item name="strategy">
              <div className="budRadioGroup">
                <InfoLabel
                  required={true}
                  text="Strategy"
                  classNames="text-nowrap h-auto bg-[transparent]"
                  content="Choose strategy"
                />
                <Radio.Group
                  value={strategy || ""}
                  onChange={(e) => setStrategy(e.target.value)}
                  className="rounded-[5px] mt-[.5rem]"
                  name="strategy"
                  options={[
                    { value: "SimpleShuffle", label: "Simple Shuffle" },
                    { value: "LeastBusy", label: "Least Busy" },
                    { value: "Advanced", label: "Advanced" },
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
