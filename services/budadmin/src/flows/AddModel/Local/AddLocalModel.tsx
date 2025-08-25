import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { use, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import {
  ModelNameInput,
  NameIconInput,
} from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import { isValidModelName } from "@/lib/utils";

function AddLocalModelForm() {
  const {
    currentWorkflow,
    setLocalModelDetails,
    localModelDetails,
    providerType,
  } = useDeployModel();
  const { form } = useContext(BudFormContext);
  const [options, setOptions] = useState([]);
  const icon = form.getFieldValue("icon");
  const name = form.getFieldValue("name");
  const uri = form.getFieldValue("uri");
  const author = form.getFieldValue("author");
  const tags = form.getFieldValue("tags");

  useEffect(() => {
    setLocalModelDetails({
      name,
      uri,
      author,
      tags,
      icon,
    });
  }, [name, uri, author, tags, icon]);

  async function fetchList(tagname) {
    await axiosInstance(`${tempApiBaseUrl}/models/tags?page=1&limit=1000`).then(
      (result) => {
        const data = result.data?.tags?.map((result) => ({
          name: result.name,
          color: result.color,
        }));
        setOptions(data);
      },
    );
  }

  useEffect(() => {
    fetchList("");
  }, []);
  useEffect(() => {
    console.log("localModelDetails", localModelDetails);
  }, [localModelDetails]);

  // useEffect(() => {
  //   console.log(currentWorkflow)
  //   console.log(currentWorkflow?.workflow_steps.provider.icon)
  // }, [currentWorkflow]);

  return (
    <BudWraperBox>
      <BudDrawerLayout>
        <DrawerTitleCard
          title={providerType?.title}
          // title="Add Huggingface model"
          description="Enter Model Information below"
        />
        <DrawerCard classNames="">
          {currentWorkflow?.workflow_steps?.provider?.type === "huggingface" ? (
            <ModelNameInput
              placeholder="Enter Model Name"
              type={currentWorkflow?.workflow_steps?.provider?.type}
              icon=""
              // icon={currentWorkflow.workflow_steps.provider.icon}
            />
          ) : (
            <NameIconInput
              placeholder="Enter Model Name"
              icon={icon || "😍"}
              onChangeIcon={(icon) => {
                form.setFieldsValue({ icon });
              }}
            />
          )}
          <TextInput
            name="uri"
            label={providerType?.id == "disk" ? "Folder Path" : "URL"}
            placeholder={
              providerType?.id == "disk" ? "Enter Folder Path" : "Enter URL"
            }
            rules={[
              {
                required: true,
                message:
                  providerType?.id == "disk"
                    ? "Please enter folder path"
                    : "Please enter URL",
              },
            ]}
            ClassNames="mt-[.4rem]"
            infoText={
              providerType?.id == "disk"
                ? "Enter a valid folder path of the model"
                : "Enter a valid URL of the model"
            }
          />
          <TextInput
            name="author"
            label="Author"
            placeholder="Enter Author name"
            rules={[{ required: true, message: "Please enter Author name" }]}
            ClassNames="mt-[.6rem]"
            formItemClassnames="pb-[.6rem]"
            infoText="Enter the Author of the model"
          />
          <TagsInput
            label="Tags"
            options={options}
            defaultValue={localModelDetails?.tags}
            info="Add keywords to help organize and find your model later."
            name="tags"
            placeholder="Select or Create tags that are relevant "
            rules={[]}
            ClassNames="mb-[0px]"
            SelectClassNames="mb-[.5rem]"
            menuplacement="top"
          />
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}

export default function AddLocalModel() {
  const { openDrawerWithStep } = useDrawer();
  const {
    currentWorkflow,
    updateModelDetailsLocal,
    updateCredentialsLocal,
    localModelDetails,
    deleteWorkflow,
    setLoading,
  } = useDeployModel();
  const { values, form } = useContext(BudFormContext);
  const [isMounted, setIsMounted] = useState(false);

  const handleNext = async () => {
    console.log("values", values);
    const result = await updateModelDetailsLocal(values);
    if (result) {
      if (currentWorkflow?.workflow_steps?.provider?.type === "huggingface") {
        console.log("trigger hug");
        return openDrawerWithStep("select-or-add-credentials");
      } else {
        setLoading(true);
        const result = await updateCredentialsLocal(null);
        if (result) {
          console.log("trigger local");
          setLoading(false);
          return openDrawerWithStep("extracting-model-status");
        }
      }
    }
  };
  // https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
  useEffect(() => {
    setIsMounted(true);
  }, []);
  return (
    <BudForm
      data={localModelDetails}
      onBack={async () => {
        await deleteWorkflow(currentWorkflow.workflow_id, true);
        openDrawerWithStep("model-source");
      }}
      disableNext={
        currentWorkflow?.workflow_steps?.provider?.type === "huggingface"
          ? !isValidModelName(values?.name) || !values?.uri || !values?.author
          : !isValidModelName(values?.name) || !values?.uri || !values?.author
      }
      onNext={handleNext}
    >
      <AddLocalModelForm />
    </BudForm>
  );
}
