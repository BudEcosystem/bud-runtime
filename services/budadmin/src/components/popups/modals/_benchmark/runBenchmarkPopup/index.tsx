import React, { useEffect, useState } from "react";
import {
  Dialog,
  Button,
  Text,
  TextField,
  Select,
  Flex,
  VisuallyHidden,
  Box,
  Tooltip,
} from "@radix-ui/themes";
import { Cross1Icon, InfoCircledIcon } from "@radix-ui/react-icons";
import {
  Text_12_300_44474D,
  Text_12_300_6A6E76,
  Text_12_400_787B83,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import {
  SelectCustomInput,
  SelectInput,
  SliderInput,
  SwitchInput,
  TextInput,
} from "@/components/ui/input";
import { ButtonInput } from "@/components/ui/button";
import ToolTip from "@/components/ui/toolTip";
import { Award } from "lucide-react";
import { useLoader } from "src/context/appContext";

interface RunBenchmarkModelProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: {}; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string }) => void;
}

interface FormData {
  name?: string;
  description?: string;
  [key: string]: string | undefined;
}

const RunBenchmarkModel: React.FC<RunBenchmarkModelProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues = {}, // Default to empty object
  onSubmit,
}) => {
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [formData, setFormData] = useState<{ [key: string]: string }>({});
  const [isCacheEnabled, setIsCacheEnabled] = useState(false);
  const [embeddingModels, setEmbeddingModels] = useState<any>([]);
  const [embeddingModel, setEmbeddingModel] = useState<any>();
  const [eviction_policy, setEviction_policy] = useState<any>();
  const [sliderValue, setSliderValue] = useState([0.5]);
  const [clusterInitialVal, setClusterInitialVal] = useState([]);
  const [clusterInfo, setClusterInfo] = useState<any>({});
  const [isTtl, setIsTtl] = useState<any>(false);
  const [clusterId, setClusterId] = useState();

  const evictionList = [
    {
      code: "LRU",
      name: "Least Recently Used",
      label: "Least Recently Used",
      description: "Evict the least recently used items first",
    },
    {
      code: "LFU",
      name: "Least Frequently Used",
      label: "Least Frequently Used",
      description: "Evict the least frequently used items first",
    },
    {
      code: "FIFO",
      name: "First In First Out",
      label: "First In First Out",
      description: "Evict the oldest items first",
    },
    {
      code: "RR",
      name: "Random Replacement",
      label: "Random Replacement",
      description: "Evict a random item",
    },
    {
      code: "TTL",
      name: "Time To Live",
      label: "Time To Live",
      description: "Evict items after a certain time period",
    },
  ];
  useEffect(() => {
    if (isOpen) {
      // setFormData(initialValues); // Set form data to initial values when modal is opened
    }
    // if (initialValues["selectedRowData"]) {
    //   setIsCacheEnabled(
    //     initialValues["selectedRowData"]["model"]["modality"] == "llm"
    //   );
    // }
    if (initialValues["modelData"]) {
      setEmbeddingModels(
        initialValues["modelData"].filter(
          (each) => each["model"]["modality"] == "embedding",
        ),
      );
    }
    if (initialValues["clusterData"]) {
      let clusterData = initialValues["clusterData"];

      let clusterVals = [];
      clusterData.forEach((cluster: any) => {
        clusterVals.push(cluster?.name);
      });

      setClusterInitialVal(clusterVals || []);
      setClusterInfo(clusterData);
    }
  }, [isOpen, initialValues]);

  const findClusterIdByName = (name: string) => {
    const cluster = clusterInfo.find((c: any) => c.name === name);
    return cluster?.id;
  };

  const handleChange = (name: any, value: any) => {
    if (name === "cluster") {
      const clusterId = findClusterIdByName(value);
      setClusterId(clusterId);
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }

    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleEmbeddingChange = (name, value) => {
    setEmbeddingModel(value);
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleSliderValueChange = (value) => {
    setFormData((prev) => ({ ...prev, ["score_threshold"]: value[0] }));
    setSliderValue(value);
    setErrors((prev) => ({ ...prev, ["score_threshold"]: undefined }));
  };

  const handleEvictionChange = (name, value) => {
    setEviction_policy(value);
    setFormData((prev) => ({ ...prev, [name]: value.code }));
    if (value.code == "TTL") {
      setIsTtl(true);
    } else {
      setIsTtl(false);
    }
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const validateForm = () => {
    const newErrors: Partial<FormData> = {};

    if (!formData.cluster) {
      newErrors.cluster = "Cluster ID is required.";
    }
    if (!formData.num_of_workers) {
      newErrors.num_of_workers = "Number of workers is required.";
    }
    if (!formData.num_of_users) {
      newErrors.num_of_users = "Number of users is required.";
    }
    if (!formData.max_new_tokens) {
      newErrors.max_new_tokens = "Max tokens is required.";
    }

    if (isCacheEnabled) {
      if (!formData.embeddingModel) {
        newErrors.embeddingModel = "Embedding model is required.";
      }
      if (!formData.max_size) {
        newErrors.max_size = "Max cache size is required.";
      }
      if (!formData.eviction_policy) {
        newErrors.eviction_policy = "Eviction policy is required.";
      }
      if (isTtl && !formData.ttl) {
        newErrors.ttl = "Days to expire is required.";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (validateForm()) {
      let data = { ...formData };
      if (data.cluster) {
        delete data.cluster;
        data.cluster_id = clusterId;
      }
      if (data.embeddingModel) {
        delete data.embeddingModel;
        data.embedding_model = embeddingModel;
      }
      data.model_id = initialValues?.["selectedRowData"]?.["model"]?.id;

      if (isCacheEnabled) {
        data.use_cache = isCacheEnabled.toString();
      }
      data.dataset = null;
      onSubmit(data);
      // onCloseDialog();
    }
  };

  const onCloseDialog = () => {
    onOpenChange(false);
    setFormData({});
    setIsCacheEnabled(false);
    setEmbeddingModel("");
    setSliderValue([0.5]);
    setEmbeddingModels([]);
    setIsTtl(false);
    setEviction_policy("");
    setClusterInitialVal([]);
    setClusterId(undefined);
    setErrors({});
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="370px"
        className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
          <VisuallyHidden>Endpoint</VisuallyHidden>
        </Dialog.Title>
        <Flex justify="between" align="start">
          <Text_16_600_FFFFFF className="p-0 m-0">{title}</Text_16_600_FFFFFF>
          <Dialog.Close>
            <Button
              className="m-0 p-0 bg-[transparent] h-[1.1rem] outline-none"
              size="1"
              onClick={onCloseDialog}
            >
              <Cross1Icon />
            </Button>
          </Dialog.Close>
        </Flex>
        <Text_12_300_44474D className="pt-[.2rem] mb-4">
          {description}
        </Text_12_300_44474D>
        <Flex direction="column" gap="3">
          <label className="pb-1 block w-full">
            <Text_12_400_787B83 className="pb-1">Cluster</Text_12_400_787B83>
            <SelectCustomInput
              size="2"
              value={formData["cluster"] || ""}
              name="cluster"
              onValueChange={(newValue) => {
                handleChange("cluster", newValue);
              }}
              triggerClassName=""
              placeholder="Select cluster"
              selectItems={clusterInitialVal}
              renderItem={""}
            />
            {errors.cluster && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.cluster}
              </Text>
            )}
          </label>
          <label className="pb-1 block w-full">
            <Text_12_400_787B83 className="pb-1 flex items-center">
              Number of workers
              <ToolTip
                align="start"
                side="bottom"
                triggerRenderItem={<InfoCircledIcon className="h-3 w-3 ml-1" />}
                arrowClasses="hidden"
                renderItemClassName="!bg-[#111113] max-w-[180px] !border !border-[1px] !border-[#212225] leading-[12px] !rounded-md"
                contentRenderItem={
                  <Text_12_300_44474D className="text-[#6A6E76]">
                    No. of replicas of the model that will be deployed. (to
                    increase throughput)
                  </Text_12_300_44474D>
                }
              />
            </Text_12_400_787B83>
            <TextInput
              textFieldSlot=""
              type="number"
              name="num_of_workers"
              value={formData?.num_of_workers || ""}
              onChange={(e) => {
                const newValue = e.target.value;
                handleChange("num_of_workers", newValue);
                setErrors((prev) => ({
                  ...prev,
                  ["num_of_workers"]: undefined,
                }));
              }}
              placeholder="Enter number of workers"
              maxLength={50}
              className="text-[#FFFFFF]"
            />
            {errors.num_of_workers && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.num_of_workers}
              </Text>
            )}
          </label>
          <label className="pb-1 block w-full">
            <Text_12_400_787B83 className="pb-1 flex items-center">
              Number of users
              <ToolTip
                align="start"
                side="bottom"
                triggerRenderItem={<InfoCircledIcon className="h-3 w-3 ml-1" />}
                arrowClasses="hidden"
                renderItemClassName="!bg-[#111113] max-w-[180px] !border !border-[1px] !border-[#212225] leading-[12px] !rounded-md"
                contentRenderItem={
                  <Text_12_300_44474D className="text-[#6A6E76]">
                    No. of concurrent users for benchmarking.
                  </Text_12_300_44474D>
                }
              />
            </Text_12_400_787B83>
            <TextInput
              textFieldSlot=""
              type="number"
              name="num_of_users"
              value={formData?.num_of_users || ""}
              onChange={(e) => {
                const newValue = e.target.value;
                handleChange("num_of_users", newValue);
                setErrors((prev) => ({
                  ...prev,
                  ["num_of_users"]: undefined,
                }));
              }}
              placeholder="Enter number of users"
              maxLength={50}
              className="text-[#FFFFFF]"
            />
            {errors.num_of_users && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.num_of_users}
              </Text>
            )}
          </label>
          <label className="block w-full">
            <Text_12_400_787B83 className="pb-1 flex items-center">
              Max tokens
              <ToolTip
                align="start"
                side="bottom"
                triggerRenderItem={<InfoCircledIcon className="h-3 w-3 ml-1" />}
                arrowClasses="hidden"
                renderItemClassName="!bg-[#111113] max-w-[180px] !border !border-[1px] !border-[#212225] leading-[12px] !rounded-md"
                contentRenderItem={
                  <Text_12_300_44474D className="text-[#6A6E76]">
                    Maximum output token expected per user.
                  </Text_12_300_44474D>
                }
              />
            </Text_12_400_787B83>
            <TextInput
              textFieldSlot=""
              type="number"
              name="max_new_tokens"
              value={formData?.max_new_tokens || ""}
              onChange={(e) => {
                const newValue = e.target.value;
                handleChange("max_new_tokens", newValue);
                setErrors((prev) => ({
                  ...prev,
                  ["max_new_tokens"]: undefined,
                }));
              }}
              placeholder="Enter maximum number of tokens"
              maxLength={50}
              className="text-[#FFFFFF]"
            />
            {errors.max_new_tokens && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.max_new_tokens}
              </Text>
            )}
          </label>
          {formData?.cluster?.length &&
            (isCacheEnabled ? (
              <Box className="bg-[#18191B] rounded-lg px-[1rem] pb-[.75rem] pt-[0.5rem]">
                <Flex align="center" gap="2" mb={"2"}>
                  <Text_12_400_787B83>Cache</Text_12_400_787B83>
                  <SwitchInput
                    className="cursor-pointer"
                    checked={isCacheEnabled}
                    onCheckedChange={(newValue) => setIsCacheEnabled(newValue)}
                  ></SwitchInput>
                </Flex>
                <Flex gap="2">
                  <label className="pb-1 block w-[55%]">
                    <Text_12_400_787B83 className="pb-1">
                      Embedding Model
                    </Text_12_400_787B83>
                    <SelectInput
                      size="2"
                      value={embeddingModel}
                      name="embeddingModel"
                      onValueChange={(newValue) => {
                        handleEmbeddingChange("embeddingModel", newValue);
                      }}
                      triggerClassName=""
                      placeholder="Select embedding model"
                      selectItems={
                        embeddingModels?.length
                          ? embeddingModels
                          : ["sentence-transformers/all-mpnet-base-v2"]
                      }
                      renderItem={""}
                      className="placeholder:text-red-500"
                    />
                    {errors.embeddingModel && (
                      <Text className="text-red-500 text-[.7rem]">
                        {errors.embeddingModel}
                      </Text>
                    )}
                  </label>
                  <label className="pb-1 block w-[45%]">
                    <Text_12_400_787B83 className="pb-1">
                      Max Cache Size
                    </Text_12_400_787B83>
                    <TextInput
                      textFieldSlot=""
                      type="number"
                      name="max_size"
                      value={formData?.["max_size"] || ""}
                      onChange={(e) => {
                        const newValue = e.target.value;
                        handleChange("max_size", newValue);
                        setErrors((prev) => ({
                          ...prev,
                          ["max_size"]: undefined,
                        }));
                      }}
                      placeholder="Enter Max tokens"
                      maxLength={50}
                      className="text-[#FFFFFF]"
                    />
                    {errors.max_size && (
                      <Text className="text-red-500 text-[.7rem]">
                        {errors.max_size}
                      </Text>
                    )}
                  </label>
                </Flex>
                <Box className="mt-2">
                  <label className="pb-1 block w-[100%]">
                    <Flex align="center" justify="between">
                      <Text_12_400_787B83 className="pb-1">
                        Scoring threshold
                      </Text_12_400_787B83>
                      <Text_12_400_787B83 className="pb-1">
                        {sliderValue}
                      </Text_12_400_787B83>
                    </Flex>

                    <SliderInput
                      defaultValue={[0.5]}
                      onValueChange={handleSliderValueChange}
                      max={1}
                      step={0.1}
                    ></SliderInput>
                    {errors.score_threshold && (
                      <Text className="text-red-500 text-[.7rem]">
                        {errors.score_threshold}
                      </Text>
                    )}
                  </label>
                </Box>
                <Flex gap="2" className="mt-2">
                  <label className="pb-1 block w-[55%]">
                    <Text_12_400_787B83 className="pb-1">
                      Eviction policy
                    </Text_12_400_787B83>
                    <SelectInput
                      size="2"
                      value={eviction_policy?.code}
                      onValueChange={(newValue) => {
                        handleEvictionChange("eviction_policy", newValue);
                      }}
                      triggerClassName=""
                      placeholder="Select eviction policy"
                      selectItems={evictionList}
                      renderItem={""}
                    />
                    {errors.eviction_policy && (
                      <Text className="text-red-500 text-[.7rem]">
                        {errors.eviction_policy}
                      </Text>
                    )}
                  </label>
                  {isTtl && (
                    <label className="pb-1 block w-[45%]">
                      <Text_12_400_787B83 className="pb-1">
                        Days to Expire
                      </Text_12_400_787B83>
                      <TextInput
                        textFieldSlot=""
                        type="number"
                        name="ttl"
                        value={formData?.["ttl"] || ""}
                        onChange={(e) => {
                          const newValue = e.target.value;
                          handleChange("ttl", newValue);
                          setErrors((prev) => ({
                            ...prev,
                            ["ttl"]: undefined,
                          }));
                        }}
                        placeholder="Enter Days"
                        maxLength={50}
                        className="text-[#FFFFFF]"
                      />
                      {errors.ttl && (
                        <Text className="text-red-500 text-[.7rem]">
                          {errors.ttl}
                        </Text>
                      )}
                    </label>
                  )}
                </Flex>
              </Box>
            ) : (
              <Flex align="center" gap="2">
                <Text_12_400_787B83>Cache</Text_12_400_787B83>
                <SwitchInput
                  className="cursor-pointer"
                  checked={isCacheEnabled}
                  onCheckedChange={(newValue) => setIsCacheEnabled(newValue)}
                ></SwitchInput>
              </Flex>
            ))}
        </Flex>
        <Flex gap="3" mt="4" justify="center">
          <Button
            size="1"
            className="h-[1.75rem] w-full text-xs font-normal"
            onClick={handleSubmit}
          >
            Run
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default RunBenchmarkModel;
