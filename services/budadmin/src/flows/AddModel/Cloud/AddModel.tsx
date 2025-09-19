import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_B3B3B3,
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
} from "@/components/ui/text";
import React, { useCallback, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Input, Image, Tag, Form, Select, ConfigProvider } from "antd"; // Added Checkbox import
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import CustomPopover from "src/flows/components/customPopover";
import { useDeployModel } from "src/stores/useDeployModel";
import { assetBaseUrl, tempApiBaseUrl } from "@/components/environment";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { modelNameRegex } from "@/lib/utils";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import ModelTags from "src/flows/components/ModelTags";
import { ModelFlowInfoCard } from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { cloudProviders, useModels } from "src/hooks/useModels";
import { useLoader } from "src/context/appContext";
import Tags from "src/flows/components/DrawerTags";

function ModelTag({ tag }) {
  return (
    <Tag
      className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem]`}
      style={{
        backgroundColor: getChromeColor("#8F55D62B"),
      }}
    >
      {tag.image && (
        <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
          <Image
            preview={false}
            src={tag.image}
            alt="info"
            style={{ width: "0.625rem", height: "0.625rem" }}
          />
        </div>
      )}
      <div
        className={`text-[0.625rem] font-[400] leading-[100%]`}
        style={{
          color: tag.color || "#B3B3B3",
        }}
      >
        {tag.name || tag}
      </div>
    </Tag>
  );
}

function AddModelForm() {
  const { form } = useContext(BudFormContext);
  const { selectedModel, setCloudModelDetails, cloudModelDetails } =
    useDeployModel();
  const [options, setOptions] = useState([]);
  const [modalityFilters, setModalityFilters] = useState(cloudProviders);

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

  return (
    <div className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      <Form.Item
        hasFeedback
        name={"name"}
        rules={[
          { required: true, message: "Please input model name!" },
          {
            pattern: modelNameRegex,
            message: "Model name should contain only alphanumeric characters",
          },
        ]}
        className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
            Model&nbsp;Name
            <CustomPopover title="This is the name of the model you want to add from the provider">
              <Image
                src="/images/info.png"
                preview={false}
                alt="info"
                style={{ width: ".75rem", height: ".75rem" }}
              />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <Input
          placeholder="Type model name"
          style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
          }}
          size="large"
          onChange={(e) => {
            form.setFieldsValue({ name: e.target.value });
            form.validateFields(["name"]);
            setCloudModelDetails({
              ...cloudModelDetails,
              name: e.target.value,
            });
          }}
          className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
        />
      </Form.Item>
      {selectedModel?.modality ? null : (
        <Form.Item
          hasFeedback
          rules={[{ required: true, message: "Please select modality!" }]}
          name={"modality"}
          className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
        >
          {/* <div className="w-full">
        <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
          Modality
          <span className="text-[red] text-[1rem]">*</span>
          <CustomPopover title="This is the modality of the model you want to add from the provider" >
            <Image
              src="/images/info.png"
              preview={false}
              alt="info"
              style={{ width: '.75rem', height: '.75rem' }}
            />
          </CustomPopover>
        </Text_12_300_EEEEEE>
      </div>
      <div className="custom-select-two w-full rounded-[6px] relative">
        <ConfigProvider
          theme={{
            token: {
              colorTextPlaceholder: '#808080',
            },
          }}
        >
          <Select
            placeholder="Select Modality"
            style={{
              backgroundColor: "transparent",
              color: "#EEEEEE",
              border: "0.5px solid #757575",
            }}
            size="large"
            className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
            options={modalityFilters.map((modality) => ({
              label: modality.label,
              value: modality.modality,
            }))}
            onChange={(value) => {
              form.setFieldsValue({ modality: value });
              form.validateFields(['modality']);
              setCloudModelDetails({
                ...cloudModelDetails,
                modality: value
              });
            }}
          />
        </ConfigProvider>
      </div> */}
          <div className="w-full">
            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
              Modality
              <CustomPopover title="This is the modality">
                <Image
                  src="/images/info.png"
                  preview={false}
                  alt="info"
                  style={{
                    width: ".75rem",
                    height: ".75rem",
                  }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
          </div>
          <div className="custom-select-two w-full rounded-[6px] relative">
            <ConfigProvider
              theme={{
                token: {
                  colorTextPlaceholder: "#808080",
                },
              }}
            >
              <Select
                placeholder="Select Modality"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                  border: "0.5px solid #757575",
                  width: "100%",
                }}
                // value={tempFilter.modality}
                maxTagCount={4}
                size="large"
                className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.15rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                options={modalityFilters.map((modality) => ({
                  label: modality.label,
                  value: modality.modality,
                }))}
                tagRender={(props) => {
                  const { label } = props;
                  return <Tags name={label} color="#D1B854"></Tags>;
                }}
                mode="multiple"
                onChange={(value) => {
                  form.setFieldsValue({ modality: value });
                  form.validateFields(["modality"]);
                  setCloudModelDetails({
                    ...cloudModelDetails,
                    modality: value,
                  });
                }}
              />
            </ConfigProvider>
          </div>
        </Form.Item>
      )}
      {selectedModel?.uri ? null : (
        <Form.Item
          hasFeedback
          name={"uri"}
          rules={[{ required: true, message: "Please input URI!" }]}
          className={`flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]`}
        >
          <div className="w-full">
            <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
              URI
              <CustomPopover title="This is the URI of the model you want to add from the provider">
                <Image
                  src="/images/info.png"
                  preview={false}
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </Text_12_300_EEEEEE>
          </div>
          <Input
            placeholder="Enter URI"
            style={{
              backgroundColor: "transparent",
              color: "#EEEEEE",
              border: "0.5px solid #757575",
            }}
            size="large"
            onChange={(e) => {
              form.setFieldsValue({ uri: e.target.value });
              form.validateFields(["uri"]);
              setCloudModelDetails({
                ...cloudModelDetails,
                uri: e.target.value,
              });
            }}
            className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
          />
        </Form.Item>
      )}
      <TagsInput
        label="Tags"
        options={options}
        defaultValue={cloudModelDetails?.tags}
        info="Add keywords to help organize and find your model later."
        name="tags"
        placeholder="Enter tags"
        rules={[]}
        onChange={(value) => {
          setCloudModelDetails({
            ...cloudModelDetails,
            tags: value,
          });
        }}
        menuplacement="top"
      />
    </div>
  );
}

export default function AddModel() {
  const {
    selectedProvider,
    selectedModel,
    currentWorkflow,
    updateCloudModelDetails,
    cloudModelDetails,
  } = useDeployModel();
  const { openDrawerWithStep } = useDrawer();
  const { getGlobalModels } = useModels();
  const { showLoader, hideLoader } = useLoader();
  const imageUrl = assetBaseUrl + selectedProvider?.icon;
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const defaultFilter = {
    name: "",
    modality: [],
    model_size_min: undefined,
    model_size_max: undefined,
    table_source: ["model"],
  };
  const [filter, setFilter] = useState<{
    name?: string;
    modality?: string[];
    model_size_min?: number;
    model_size_max?: number;
    table_source?: string[];
  }>(defaultFilter);
  const load = useCallback(
    async (filter) => {
      showLoader();
      await getGlobalModels({
        page: currentPage,
        limit: pageSize,
        name: filter.name,
        tag: filter.name,
        // description: filter.name,
        modality: filter.modality?.length > 0 ? filter.modality : undefined,
        tasks: filter.tasks?.length > 0 ? filter.tasks : undefined,
        author: filter.author?.length > 0 ? filter.author : undefined,
        model_size_min: isFinite(filter.model_size_min)
          ? filter.model_size_min
          : undefined,
        model_size_max: isFinite(filter.model_size_max)
          ? filter.model_size_max
          : undefined,
        // table_source: filter.table_source,
        table_source: "model",
      });
      hideLoader();
    },
    [currentPage, pageSize, getGlobalModels],
  );

  return (
    <BudForm
      data={{}}
      disableNext={selectedModel?.uri ? false : !cloudModelDetails?.uri}
      // disableNext={!cloudModelDetails?.modality || (selectedModel?.uri ? false : !cloudModelDetails?.uri)}
      onNext={async () => {
        if (!currentWorkflow) {
          return openDrawerWithStep("model-source");
        } else {
          await updateCloudModelDetails().then((response) => {
            if (response) {
              load(filter);
              openDrawerWithStep("cloud-model-success");
            }
          });
        }
      }}
      onBack={() => {
        openDrawerWithStep("model-list");
      }}
    >
      <BudWraperBox>
        {selectedModel && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title={selectedModel ? "Selected Model" : "Provider"}
              description={
                selectedModel
                  ? `From ${selectedProvider.name} the following model has been selected`
                  : "Below is the cloud provider you have selected"
              }
            />
            <ModelFlowInfoCard
              selectedModel={selectedModel}
              informationSpecs={[
                {
                  name: "URI",
                  value: selectedModel?.uri,
                  full: true,
                  icon: "/images/drawer/tag.png",
                },
              ]}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <DrawerTitleCard
            title={
              selectedModel
                ? "Give this model a name you recognize"
                : "Add Model"
            }
            description={`Type the name of the model you want to add from ${selectedProvider?.name}.`}
          />
          <AddModelForm />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
