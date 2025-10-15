import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import TextInput from "../components/TextInput";
import { PaperPublished, useModels } from "src/hooks/useModels";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Tag } from "antd";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { errorToast, successToast } from "@/components/toast";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import FileInput from "../components/FileInput";
import { ModelNameInput } from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { isValidModelName, isValidUrl } from "@/lib/utils";
import Tags from "../components/DrawerTags";

function EditModelForm({
  formData,
  setFormData,
}: {
  formData: FormData;
  setFormData: any;
}) {
  const [url, setUrl] = useState<string>("");
  const [urls, setUrls] = useState<PaperPublished[]>([]);
  const { selectedModel, modelValues, setModelValues } = useModels();
  const { values = {} } = useContext(BudFormContext);

  const [options, setOptions] = useState([]);

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
    setFormData(new FormData());
  }, []);

  useEffect(() => {
    if (selectedModel) {
      setModelValues({
        ...selectedModel,
      });
      setUrls(selectedModel?.paper_published);
    } else {
      setModelValues({});
    }
  }, [selectedModel]);

  const validURL = url && isValidUrl(url);

  return (
    <BudWraperBox>
      <BudDrawerLayout>
        <DrawerTitleCard
          title="Edit Model"
          description="Make changes to the model information"
        />
        <DrawerCard classNames="pb-0">
          <ModelNameInput
            placeholder="Enter Model Name"
            icon={selectedModel?.icon}
            onChange={(name) => {
              formData.set("name", name);
              setFormData(formData);
            }}
          />
          <div className="mt-[.5rem]">
            <div>
              <TagsInput
                defaultValue={selectedModel?.tags}
                info="Enter Tags"
                name="tags"
                placeholder="Enter tags"
                rules={[]}
                onChange={(value) => {
                  formData.set("tags", JSON.stringify(value));
                  setFormData(formData);
                }}
                label="Tags"
                options={options}
                required
              />
            </div>
            <div className="mt-[1.3rem]">
              <TagsInput
                defaultValue={selectedModel?.tasks}
                name="tasks"
                label="Tasks"
                info="Enter Tasks"
                placeholder="Enter Tasks"
                rules={[]} // { required: true, message: "Please enter Tasks" }
                onChange={(value) => {
                  formData.set("tasks", JSON.stringify(value));
                }}
                options={options}
                // required
              />
            </div>
            <div className="mt-[.7rem]">
              <TextAreaInput
                name="description"
                label="Model Description"
                // required
                info="Write Description Here"
                placeholder="Write Description Here,"
                rules={[]} // { required: true, message: "Please enter description", }
                value={values.description}
                onChange={(value) => {
                  formData.set("description", value);
                  setFormData(formData);
                }}
              />
            </div>
          </div>
          <DrawerTitleCard
            title="Paper Published"
            description="Add research paper associated with the model"
            classNames="!pl-[0] !pt-[1.3rem]"
          />
          <div className="mt-[.5rem]">
            <div>
              <TextInput
                name="paper_urls"
                label="URL"
                infoText="Enter the URL of the paper"
                placeholder="Enter URL"
                value={url}
                rules={[{ required: false, message: "Please enter Url" }]}
                InputClasses="pt-[.75rem] pb-[.75rem]"
                onChange={(value) => {
                  setUrl(value);
                }}
                suffix={
                  validURL ? (
                    <PrimaryButton
                      onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        if (!isValidUrl(url)) {
                          errorToast("Invalid URL");
                          return;
                        }
                        if (urls?.find((item) => item.url === url)) {
                          errorToast("URL already added");
                          setUrl("");
                          return;
                        }

                        const update = [
                          ...(urls || []),
                          {
                            id: "",
                            model_id: "",
                            title: url,
                            url: url,
                          },
                        ];
                        setUrls(update);
                        setUrl("");
                        formData.set(
                          "paper_urls",
                          update?.map((item) => item.url).join(","),
                        );
                      }}
                    >
                      Add Link
                    </PrimaryButton>
                  ) : (
                    <SecondaryButton disabled>Add Link</SecondaryButton>
                  )
                }
              />
            </div>
            <div className="mt-[1rem] flex flex-wrap flex-auto justify-start items-center gap-[.4rem]">
              {urls?.map((url, index) => {
                return (
                  <Tags
                    key={index}
                    name={`${url.title}-${index}`}
                    color="#D1B854"
                    classNames="w-100% truncate"
                    textClass="w-100% truncate"
                    closable
                    onClose={() => {
                      const update = urls.filter((item, i) => i !== index);
                      setUrls(update);
                      formData.set(
                        "paper_urls",
                        update?.map((item) => item.url).join(","),
                      );
                    }}
                  />
                );
              })}
            </div>
          </div>
          <DrawerTitleCard
            title="Model Links"
            description="Enter model detail links below"
            classNames="!pl-[0] !pt-[1.3rem]"
          />
          <div className="mt-[.5rem]">
            <div>
              <TextInput
                name="github_url"
                infoText="Enter the Github URL of the model"
                label="Github Link"
                placeholder="Enter Github Link"
                rules={[
                  { required: false, message: "Please enter Github Link" },
                  {
                    pattern: new RegExp(/^(http|https):\/\/[^ "]+$/),
                    message: "Please enter a valid URL",
                  },
                ]}
                onChange={(value) => {
                  formData.set("github_url", value);
                  setFormData(formData);
                }}
              />
            </div>
            <div>
              <TextInput
                name="huggingface_url"
                infoText="Enter the Huggingface URL of the model"
                label="Huggingface LInk"
                placeholder="Enter Huggingface LInk"
                rules={[
                  { required: false, message: "Please enter Huggingface LInk" },
                  {
                    pattern: new RegExp(/^(http|https):\/\/[^ "]+$/),
                    message: "Please enter a valid URL",
                  },
                ]}
                onChange={(value) => {
                  formData.set("huggingface_url", value);
                  setFormData(formData);
                }}
              />
            </div>
            <div>
              <TextInput
                name="website_url"
                infoText="Enter the Website URL of the model"
                label="Website Link"
                placeholder="Enter Website Link"
                rules={[
                  { required: false, message: "Please enter Website Link" },
                  {
                    pattern: new RegExp(/^(http|https):\/\/[^ "]+$/),
                    message: "Please enter a valid URL",
                  },
                ]}
                onChange={(value) => {
                  formData.set("website_url", value);
                  setFormData(formData);
                }}
              />
            </div>
          </div>
          <DrawerTitleCard
            title="Add License"
            description="Upload license information or enter URL "
            classNames="!pl-[0] !pt-[1.3rem]"
          />
          <div className="mt-[1rem] mb-[1rem]"></div>
          {modelValues.model_licenses && selectedModel?.model_licenses?.name ? (
            <div className="flex items-center gap-[1rem] ">
              <Tags
                color="#D1B854"
                name={selectedModel?.model_licenses?.name}
                closable
                classNames="customTags"
                // onClose={() => {
                //   // formData.set("license_url", null);
                //   formData.delete("license_file");
                //   setFormData(formData);
                //   setModelValues({
                //     ...modelValues,
                //     model_licenses: null,
                //   });
                onClose={() => {
                  formData.delete("license_url"); // delete the license URL if it exists
                  formData.delete("license_file"); // delete the uploaded file
                  formData.set("remove_license", "true"); // optionally inform backend license was removed
                  setFormData(formData); // update the formData

                  setModelValues({
                    ...modelValues,
                    model_licenses: null,
                  });
                }}
              />
            </div>
          ) : (
            <>
              <FileInput
                name="license_file"
                acceptedFileTypes={[".md", ".pdf", ".txt"]}
                label="Upload File"
                placeholder=""
                required
                infoText="Upload License File"
                text={
                  <>
                    Drag & Drop or <b>Choose file</b> to upload
                  </>
                }
                hint={
                  <>
                    <div className="text-[.75rem] pt-[.3rem]">
                      Supported formats : Markdown, PDF, Text
                    </div>
                    <div className="text-[.675rem]">
                      Maximum file size : 10 MB
                    </div>
                  </>
                }
                rules={[
                  {
                    required: !formData.get("license_url"),
                    message: "Please upload a file",
                  },
                ]}
                onChange={(value) => {
                  setFormData((prev) => {
                    prev.set("license_file", value);
                    return prev;
                  });
                }}
              />
              <div className="flex justify-between items-center gap-[1rem] mb-[1rem]">
                <div className="bg-[#757575] h-[1px] w-[47%]"></div>
                <div className="text-[.75rem] text-[#FFFFFF] font-[600]">
                  OR
                </div>
                <div className="bg-[#757575] h-[1px] w-[47%]"></div>
              </div>
              <div>
                <TextInput
                  name="license_url"
                  infoText="Enter the URL of the license"
                  label="URL"
                  placeholder="Enter URL"
                  rules={[
                    {
                      required: !formData.get("license_file"),
                      message: "Please enter Website Link",
                    },
                    {
                      pattern: new RegExp(/^(http|https):\/\/[^ "]+$/),
                      message: "Please enter a valid URL",
                    },
                  ]}
                  onChange={(value) => {
                    formData.set("license_url", value);
                    setFormData(formData);
                  }}
                  onBlur={() => {
                    const url = formData.get("license_url");
                    if (!isValidUrl(url)) {
                      errorToast("Invalid URL");
                      formData.delete("license_url");
                      setFormData(formData);
                      return;
                    }
                  }}
                />
              </div>
            </>
          )}
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}

export default function EditModel() {
  const { values } = useContext(BudFormContext);
  const [formData, setFormData] = useState<FormData>(new FormData());
  const { openDrawer } = useDrawer();
  const {
    modelValues,
    setModelValues,
    selectedModel,
    updateModel,
    refresh,
    getModel,
  } = useModels();
  useEffect(() => {
    setModelValues({
      ...modelValues,
      ...selectedModel,
    });
  }, [selectedModel]);

  if (!selectedModel) {
    return null;
  }

  return (
    <BudForm
      backText="Cancel"
      nextText="Save"
      disableNext={!isValidModelName(values?.name)}
      onBack={() => openDrawer("view-model")}
      onNext={async () => {
        console.log("formData", formData.get("license_file"));
        console.log("formData", formData.get("license_url"));
        if (formData.get("license_file") && formData.get("license_url")) {
          errorToast("Please either upload a file or enter an url");
          return;
        }
        const result = await updateModel(selectedModel?.id, formData);
        if (result) {
          successToast("Model Updated Successfully");
          await getModel(selectedModel?.id);
          refresh();
          openDrawer("view-model");
        }
      }}
      data={{
        ...selectedModel,
        icon: selectedModel?.icon?.length > 1 ? "🌐" : selectedModel?.icon,
      }}
    >
      <EditModelForm formData={formData} setFormData={setFormData} />
    </BudForm>
  );
}
