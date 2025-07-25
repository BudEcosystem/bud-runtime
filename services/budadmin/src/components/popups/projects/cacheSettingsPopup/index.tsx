import React, { useCallback, useEffect, useState } from "react";
import { Dialog, Button, Text, TextField, Flex, Box, VisuallyHidden } from "@radix-ui/themes";
import { Cross1Icon } from "@radix-ui/react-icons";
import {
  SelectInput,
  SliderInput,
  TextAreaInput,
  TextInput,
} from "@/components/ui/input";
import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import { errorToast } from "@/components/toast";

interface CacheSettingsPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: any; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string }) => void;
  // saveForm: (formData: { [key: string]: string }) => void;
}

interface FormData {
  name?: string;
  description?: string;
  [key: string]: string | undefined;
}

const CacheSettingsPopup: React.FC<CacheSettingsPopupProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues = {},
  onSubmit,
  // saveForm
}) => {
  const [formData, setFormData] = useState<any>({...initialValues?.cachedValues, 
    maxCache: initialValues.cachedValues.maxCache || 1000,
  });
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [sliderValue, setSliderValue] = useState(initialValues.cachedValues.score || [0.90]);
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
  // const handleChange = (e: { target: { name: string; value: string } }) => {
  //   const { name, value } = e.target;
  //   const newErrors = { ...errors };
  //   if (name === "name" && value.trim() === "") {
  //     newErrors.name = "Project name is required";
  //   } else if (name === "description" && value.trim().split(' ').length > 50) {
  //     newErrors.description = "Description cannot exceed 50 words";
  //   } else {
  //     delete newErrors[name];
  //   }
  //   setFormData((prevData) => ({
  //     ...prevData,
  //     [name]: value,
  //   }));
  //   setErrors(newErrors);
  // };

  const defaultEvictionPolicy = evictionList.find(
    (policy) => policy.code === 'LFU'
  );
  const EmbeddingModel = [
    {
      model: {
        name: 'sentence-transformers/all-mpnet-base-v2',
        uri: 'sentence-transformers/all-mpnet-base-v2',
      },
    },
  ];
  const defaultEmbeddingModle = EmbeddingModel.find(
    (obj) => obj.model.name === 'sentence-transformers/all-mpnet-base-v2'
  );
  const [embeddingModel, setEmbeddingModel] = useState<any>(defaultEmbeddingModle);
  const [evictionPolicy, setEvictionPolicy] = useState<any>(initialValues.cachedValues.evictionPolicy ? 
    evictionList?.filter((el: any)=> el.name === initialValues.cachedValues.evictionPolicy)[0] : defaultEvictionPolicy);
  const [isTtl, setIsTtl] = useState<any>(evictionList?.filter((el: any)=> el.name === initialValues?.cachedValues?.evictionPolicy)[0]?.code === 'TTL');

  const handleSubmitCache = () => {
    onSubmit(formData);
  };

  const handleChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };
  const handleEmbeddingChange = (name, value) => {
    setEmbeddingModel(value);
    setFormData((prev) => ({ ...prev, [name]: value.uri }));
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

  const handleSliderValueChange = (value) => {
    setFormData((prev) => ({ ...prev, ["score"]: value }));
    setSliderValue(value);
  };

  const onDialogClose = useCallback(() => {
    setFormData(initialValues?.cachedValues);
    setEmbeddingModel("");
    setEvictionPolicy("");
    setSliderValue([0.90]);
    setErrors({});
  }, [
    setFormData,
    initialValues,
    setEmbeddingModel,
    setEvictionPolicy,
    setSliderValue,
    setErrors,
  ]);

  useEffect(()=>{
    if(initialValues.cachedValues) {
      const prevVal = {
        embeddingModel : initialValues.cachedValues.embeddingModel,
        evictionPolicy : initialValues.cachedValues.evictionPolicy
      }      
      setFormData({...formData, ...initialValues.cachedValues})
    }
  }, [initialValues.cachedValues])

  useEffect(() => {
    if (!isOpen) {
      onDialogClose();
    }
  }, [isOpen, onDialogClose]);

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
  }, [defaultEvictionPolicy, defaultEmbeddingModle, formData]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="370px"
        className="w-[29%] p-[1.5rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
            <VisuallyHidden>Endpoint</VisuallyHidden>
          </Dialog.Title>
        <Box className="pb-3">
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
        </Box>
        <Box>
          <Flex gap="2">
            <label className="pb-1 block w-[55%]">
              <Text_12_400_787B83 className="pb-1">
                Embedding Model
              </Text_12_400_787B83>
              <SelectInput
                size="2"
                value={embeddingModel?.model?.name}
                name="embeddingModel"
                onValueChange={(newValue) => {
                  handleEmbeddingChange("embeddingModel", newValue);
                }}
                triggerClassName=""
                placeholder="Select embedding model"
                selectItems={initialValues.modalData}
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
                value={formData?.maxCache || ""}
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
                defaultValue={[0.90]}
                value={formData.score}
                onValueChange={handleSliderValueChange}
                max={1}
                step={0.1}
              ></SliderInput>
            </label>
          </Box>
          <Flex gap="2" className="mt-2 mb-6">
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
                <Text className="text-red-500 text-[.7rem]">{errors.name}</Text>
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
                  value={formData?.ttl || ""}
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

        <Flex gap="3" mt="4" justify="center">
          <Button
            size="1"
            className="h-[1.75rem] w-full text-xs font-normal"
            onClick={handleSubmitCache}
          >
            Done
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default CacheSettingsPopup;
