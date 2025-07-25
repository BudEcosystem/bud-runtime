import React, { useContext, useEffect, useState } from "react";
import { Form, Select, ConfigProvider } from "antd";
import { useRouter } from "next/router";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { successToast } from "@/components/toast";
import { Text_12_300_EEEEEE } from "@/components/ui/text";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useModels } from "src/hooks/useModels";
import { useDrawer } from "src/hooks/useDrawer";
import TextInput from "src/flows/components/TextInput";
import CustomSelect from "src/flows/components/CustomSelect";

const NewExperimentForm = () => {
  const { form } = useContext(BudFormContext);
  const { models, getGlobalModels } = useModels();
  const [modelOptions, setModelOptions] = useState([]);
  const [options, setOptions] = useState([]);


  useEffect(() => {
    // Fetch models for the dropdown
    getGlobalModels({
      page: 1,
      limit: 100,
      table_source: "model",
    });
  }, []);

  useEffect(() => {
    if (models && models.length > 0) {
      const options = models.map((model) => ({
        label: model.name,
        value: model.id,
      }));
      setModelOptions(options);
    }
  }, [models]);

  return (
    <DrawerCard>
      <TextInput
        name="experimentName"
        label="Experiment Name"
        placeholder="Type experiment name"
        infoText="Experiment name must not exceed 100 characters"
        rules={[
          { required: true, message: "Experiment name is required" },
          { min: 3, message: "Experiment name must be at least 3 characters" },
          { max: 100, message: "Experiment name must not exceed 100 characters" }
        ]}
        ClassNames="mt-[.4rem]"
        InputClasses="py-[.5rem]"
      />
      <TagsInput
        label="Tags"
        options={options}
        info="Add keywords to help organize and find your model later."
        name="tags" placeholder="Select or Create tags that are relevant " rules={[]}
        ClassNames="mb-[0px]" SelectClassNames="mb-[.5rem]" menuplacement="top"
      />
      <TextAreaInput
        name="description"
        label="Description"
        required
        info="This is the experiments’s elevator pitch, use clear and concise words to summarize the project in few sentences"
        placeholder="Provide a brief description about the experiment."
        rules={[{ required: true, message: "Provide a brief description about the experiment." }]}
      />
       <CustomSelect
        name="Model"
        label="Model"
        info="select Model"
        placeholder="Select Model"
      />
    </DrawerCard>
  );
};

export default function NewExperimentDrawer() {
  const router = useRouter();
  const { closeDrawer } = useDrawer();

  const handleSubmit = async (values: any) => {
    try {
      // TODO: Replace with actual API call to create experiment
      console.log("Creating experiment with values:", values);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      successToast("Experiment created successfully");
      closeDrawer();

      // Refresh the experiments list or navigate to the new experiment
      router.push("/home/evaluations");
    } catch (error) {
      console.error("Failed to create experiment:", error);
    }
  };

  return (
    <BudForm
      data={{
        experimentName: "",
        tags: [],
        description: "",
        model: undefined,
      }}
      onNext={handleSubmit}
      nextText="Create"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="New Experiment"
            description="A route allows you to create a custom OpenAI Compatible endpoint, with a swarm of models working together based on"
          />
          <NewExperimentForm />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}