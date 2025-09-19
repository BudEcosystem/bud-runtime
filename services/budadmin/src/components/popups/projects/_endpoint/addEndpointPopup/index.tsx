import React, { useEffect, useState } from "react";
import {
  Dialog,
  Button,
  Text,
  TextField,
  Flex,
  Box,
  VisuallyHidden,
} from "@radix-ui/themes";
import { Cross1Icon } from "@radix-ui/react-icons";
import {
  SelectInput,
  SliderInput,
  SwitchInput,
  TextAreaInput,
  TextInput,
} from "@/components/ui/input";
import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import { number } from "echarts";

interface AddEndpointPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: any; // Optional initial values for edit functionality
  defaultEvictionPolicy?: { name: string };
  defaultEmbeddingModle?: { model: { uri: string } };
  defaultMaxCache?: string;
  onSubmit: (formData: { [key: string]: any }) => void;
}

interface FormData {
  name?: string;
  description?: string;
  evictionPolicy?: any;
  embeddingModel?: any;
  maxCache?: any;
  cacheEnabled?: any;
  [key: string]: any | undefined;
}

const AddEndpointPopup: React.FC<AddEndpointPopupProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues,
  onSubmit,
}) => {
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
  const defaultEvictionPolicy = evictionList.find(
    (policy) => policy.code === "LFU",
  );
  const EmbeddingModel = [
    {
      model: {
        name: "sentence-transformers/all-mpnet-base-v2",
        uri: "sentence-transformers/all-mpnet-base-v2",
      },
    },
  ];
  const defaultEmbeddingModle = EmbeddingModel.find(
    (obj) => obj.model.name === "sentence-transformers/all-mpnet-base-v2",
  );
  const defaultMaxCache = 1000;
  const [isDeployButtonEnabled, setIsDeployButtonEnabled] = useState(false);
  const [modelData, setModelData] = useState(initialValues.modelData);
  const [selectedModel, setSelectedModel] = useState<any>([]);
  const [clusterData, setClusterData] = useState();
  const [selectedCluster, setSelectedCluster] = useState<any>(
    initialValues.clusterData,
  );
  const [workerCount, setworkerCount] = useState<any>(1);
  const [formData, setFormData] = useState({
    evictionPolicy: "",
    embeddingModel: "",
    maxCache: 1000,
    cacheEnabled: false,
  });
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [isCacheVisible, setIsCacheVisible] = useState(false);
  const [displayCache, setDisplayCache] = useState(false);
  const [isTtl, setIsTtl] = useState<any>(false);
  const [embeddingModels, setEmbeddingModels] = useState<any>([]);
  const [embeddingModel, setEmbeddingModel] = useState<any>(
    defaultEmbeddingModle,
  );
  const [evictionPolicy, setEvictionPolicy] = useState<any>(
    defaultEvictionPolicy,
  );
  const [sliderValue, setSliderValue] = useState([0.9]);

  useEffect(() => {
    if (initialValues) {
      setModelData(initialValues.modelData);
      setClusterData(initialValues.clusterData);
    }
  }, [initialValues]);
  // Assuming defaultEvictionPolicy, defaultEmbeddingModle, and defaultMaxCache are coming from props or context
  useEffect(() => {
    let updated = false;
    if (defaultEvictionPolicy && !formData.evictionPolicy) {
      setFormData((prev) => {
        if (prev.evictionPolicy !== defaultEvictionPolicy.name) {
          updated = true;
          return { ...prev, evictionPolicy: defaultEvictionPolicy.name };
        }
        return prev;
      });
    }

    if (defaultEmbeddingModle && !formData.embeddingModel) {
      setFormData((prev) => {
        if (prev.embeddingModel !== defaultEmbeddingModle.model.uri) {
          updated = true;
          return { ...prev, embeddingModel: defaultEmbeddingModle.model.uri };
        }
        return prev;
      });
    }

    if (defaultMaxCache && !formData.maxCache) {
      setFormData((prev) => {
        if (prev.maxCache !== defaultMaxCache) {
          updated = true;
          return { ...prev, maxCache: defaultMaxCache };
        }
        return prev;
      });
    }
  }, [defaultEvictionPolicy, defaultEmbeddingModle, defaultMaxCache, formData]);

  const handleChange = (name, value) => {
    setFormData((prevData) => ({
      ...prevData,
      workers: 1,
      [name]: value,
    }));
  };

  const handleSubmit = () => {
    onSubmit(formData);
  };

  const handleEmbeddingChange = (name, value) => {
    setEmbeddingModel(value);
    setFormData((prev) => ({ ...prev, [name]: value.uri }));
  };

  const handleSliderValueChange = (value) => {
    setFormData((prev) => ({ ...prev, ["score"]: value }));
    setSliderValue(value);
  };
  const handleEvictionChange = (name, value) => {
    setEvictionPolicy(value);
    setFormData((prev) => ({ ...prev, [name]: value.name }));
    if (value.code == "TTL") {
      setIsTtl(true);
    } else {
      setIsTtl(false);
    }
  };

  const onDialogClose = () => {
    setErrors({});
  };

  useEffect(() => {
    if (!isOpen) {
      onDialogClose();
    }
  }, [isOpen]);

  useEffect(() => {
    if (modelData) {
      setEmbeddingModels(
        modelData.filter((each) => each.modality == "embedding"),
      );
    }
  }, [modelData]);
  useEffect(() => {
    const isModelSelected = !!selectedModel?.["model"]?.["name"];
    const isClusterSelected = !!selectedCluster?.["name"];
    const isWorkerCountValid = !!workerCount;

    if (isModelSelected && isClusterSelected && isWorkerCountValid) {
      setIsDeployButtonEnabled(true);
    } else {
      setIsDeployButtonEnabled(false);
    }
  }, [selectedModel, selectedCluster, workerCount]);

  useEffect(() => {
    if (selectedModel) {
      setDisplayCache(selectedModel?.model?.modality === "llm");
      setFormData({
        ...formData,
        cacheEnabled:
          selectedModel?.model?.modality != "llm" || !isCacheVisible
            ? false
            : true,
      });
    }
  }, [selectedModel]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="400px"
        className="w-[32%] p-[1rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
          <VisuallyHidden>Add Endpoint</VisuallyHidden>
        </Dialog.Title>
        <Box className="px-[.75rem] pb-3">
          <Flex justify="between" align="center">
            <Text_16_600_FFFFFF className="p-0 pt-1 m-0">
              {title}
            </Text_16_600_FFFFFF>
            <Dialog.Close>
              <Button
                className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem]"
                size="1"
              >
                <Cross1Icon className="text-[#787B83]" />
              </Button>
            </Dialog.Close>
          </Flex>
          <Text_12_300_44474D className="pt-2" mb="3">
            {description}
          </Text_12_300_44474D>
        </Box>
        <Box>
          <Flex gap="1" className="px-[.75rem]">
            <Box className="max-w-[33.3%]">
              <Text_12_400_787B83 className="pb-1">Model</Text_12_400_787B83>
              <SelectInput
                size="2"
                value={selectedModel?.["model"]?.["name"]}
                onValueChange={(newValue) => {
                  setSelectedModel(newValue);
                  handleChange("model", newValue);
                }}
                placeholder="Select Model"
                selectItems={modelData}
                renderItem=""
              />
            </Box>
            <Box className="max-w-[33.3%]">
              <Text_12_400_787B83 className="pb-1">Cluster</Text_12_400_787B83>
              {/* {clusterData?.length > 0 && ( */}
              <SelectInput
                size="2"
                value={selectedCluster["name"]}
                onValueChange={(newValue) => {
                  setSelectedCluster(newValue);
                  handleChange("cluster", newValue);
                }}
                placeholder="Select Cluster"
                selectItems={clusterData}
                renderItem=""
              />
              {/* )} */}
            </Box>
            <Box className="max-w-[33.3%]">
              <Text_12_400_787B83 className="pb-1">Workers</Text_12_400_787B83>
              <TextInput
                textFieldSlot=""
                name="name"
                value={workerCount}
                onChange={(e) => {
                  const newValue = e.target.value;
                  setworkerCount(newValue);
                  handleChange("workers", Number(newValue));
                }}
                placeholder="Enter Workers"
                maxLength={50}
                className="text-[#FFFFFF]"
              />
            </Box>
          </Flex>
          {displayCache && (
            <>
              {isCacheVisible ? (
                <Box className="bg-[#18191B] rounded-lg px-[1rem] pb-[.75rem] mt-[1rem]">
                  <Flex align="center" gap="2" className="py-3">
                    <Text_12_400_787B83>Cache</Text_12_400_787B83>
                    <SwitchInput
                      className="cursor-pointer"
                      checked={isCacheVisible}
                      onCheckedChange={(newValue) => {
                        setIsCacheVisible(newValue);
                        handleChange("cacheEnabled", newValue);
                      }}
                    ></SwitchInput>
                  </Flex>
                  <Flex gap="2">
                    <label className="pb-1 block w-[55%]">
                      <Text_12_400_787B83 className="pb-1">
                        Embedding Model
                      </Text_12_400_787B83>
                      <SelectInput
                        size="2"
                        value={embeddingModel?.model.name}
                        name="embeddingModel"
                        onValueChange={(newValue) => {
                          handleEmbeddingChange("embeddingModel", newValue);
                        }}
                        triggerClassName=""
                        placeholder="Select embedding model"
                        selectItems={embeddingModels}
                        className="truncate"
                        renderItem={""}
                      />
                    </label>
                    <label className="pb-1 block w-[45%]">
                      <Text_12_400_787B83 className="pb-1">
                        Max Cache Size
                      </Text_12_400_787B83>
                      <TextInput
                        textFieldSlot=""
                        name="maxCache"
                        value={formData?.["maxCache"] || ""}
                        onChange={(e) => {
                          const newValue = e.target.value;
                          handleChange("maxCache", newValue);
                        }}
                        placeholder="Enter Max tokens"
                        maxLength={50}
                        className="text-[#FFFFFF]"
                      />
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
                        defaultValue={[0.9]}
                        onValueChange={handleSliderValueChange}
                        max={1}
                        step={0.01}
                      ></SliderInput>
                    </label>
                  </Box>
                  <Flex gap="2" className="mt-2">
                    <label className="pb-1 block w-[55%]">
                      <Text_12_400_787B83 className="pb-1">
                        Eviction policy
                      </Text_12_400_787B83>
                      <SelectInput
                        size="2"
                        value={evictionPolicy?.code}
                        onValueChange={(newValue) => {
                          handleEvictionChange("evictionPolicy", newValue);
                        }}
                        triggerClassName=""
                        placeholder="Select eviction policy"
                        selectItems={evictionList}
                        renderItem={""}
                      />
                      {errors.name && (
                        <Text className="text-red-500 text-[.7rem]">
                          {errors.name}
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
                          name="ttl"
                          value={formData?.["ttl"] || ""}
                          onChange={(e) => {
                            const newValue = e.target.value;
                            handleChange("ttl", newValue);
                          }}
                          placeholder="Enter Days"
                          maxLength={50}
                          className="text-[#FFFFFF]"
                        />
                      </label>
                    )}
                  </Flex>
                </Box>
              ) : (
                <Flex align="center" gap="2" className="pt-3 px-[.75rem]">
                  <Text_12_400_787B83>Cache</Text_12_400_787B83>
                  <SwitchInput
                    className="cursor-pointer"
                    checked={isCacheVisible}
                    onCheckedChange={(newValue) => {
                      setIsCacheVisible(newValue);
                      handleChange("cacheEnabled", newValue);
                    }}
                  ></SwitchInput>
                </Flex>
              )}
            </>
          )}
        </Box>

        <Flex gap="3" mt="4" justify="center" className="px-[.75rem]">
          <Button
            size="1"
            className="h-[1.75rem] w-full text-xs font-normal"
            onClick={handleSubmit}
            disabled={!isDeployButtonEnabled}
          >
            Deploy
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default AddEndpointPopup;
