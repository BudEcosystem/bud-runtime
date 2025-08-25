import React, { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  Button,
  Text,
  Flex,
  Box,
  VisuallyHidden,
} from "@radix-ui/themes";
import { CheckIcon, Cross1Icon } from "@radix-ui/react-icons";
import { FileInput, SelectInput, TextInput } from "@/components/ui/input";
import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";
import * as Checkbox from "@radix-ui/react-checkbox";

interface AddClusterPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: {}; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string | File[] | boolean }) => void;
}

interface FormData {
  name?: string;
  type?: string;
  configuration?: File[];
  enable_master_node?: boolean;
  [key: string]: string | File[] | undefined | boolean;
}

interface FormErrors {
  name?: string;
  type?: string;
  configuration?: string;
  enable_master_node?: string;
}

const AddClusterPopup: React.FC<AddClusterPopupProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues = {},
  onSubmit,
}) => {
  const options = [
    { label: "CPU", value: "cpu" },
    { label: "GPU", value: "gpu" },
    { label: "HPU", value: "hpu" },
  ];
  const [formData, setFormData] = useState<FormData>(initialValues);
  const [errors, setErrors] = useState<FormErrors>({});

  const handleFilesSelected = (files: File[]) => {
    if (
      files.some(
        (file) =>
          file.type !== "application/x-yaml" && !file.name.endsWith(".yaml"),
      )
    ) {
      setErrors((prevErrors) => ({
        ...prevErrors,
        configuration: "Invalid file type. Only .yaml files are allowed.",
      }));
      setFormData((prevData) => ({ ...prevData, configuration: undefined }));
    } else {
      setErrors((prevErrors) => ({
        ...prevErrors,
        configuration:
          files.length <= 0 ? "Configuration file is required" : undefined,
      }));
      setFormData((prevData) => ({ ...prevData, configuration: files }));
    }
  };

  const handleChange = (name: string, value: any) => {
    const newErrors = { ...errors };
    if (value.trim() === "") {
      newErrors[name] =
        `${name.charAt(0).toUpperCase() + name.slice(1)} is required`;
    } else {
      delete newErrors[name]; // Clear error if input is valid
    }
    setFormData((prevData) => ({
      ...prevData,
      [name]: value,
    }));
    setErrors(newErrors);
  };

  const handleCheck = (name: string, value: any) => {
    const newErrors = { ...errors };
    setFormData((prevData) => ({
      ...prevData,
      [name]: value,
    }));
    setErrors(newErrors);
  };

  const isFormValid = () => {
    return (
      formData.name &&
      formData.type &&
      formData.configuration &&
      !errors.configuration
    );
  };

  const handleSubmit = () => {
    if (isFormValid()) {
      onSubmit(formData);
    } else {
      const newErrors = { ...errors };
      if (!formData?.name) {
        newErrors.name = "Cluster name is required";
      }
      if (!formData?.type) {
        newErrors.type = "Cluster type is required";
      }
      if (
        (!formData.configuration || formData?.configuration?.length <= 0) &&
        !errors.configuration
      ) {
        newErrors.configuration = "Configuration file is required";
      }
      setErrors(newErrors);
    }
  };

  const onDialogClose = useCallback(() => {
    setErrors({});
    setFormData(initialValues);
  }, [initialValues]);

  useEffect(() => {
    if (!isOpen) {
      onDialogClose();
    } else {
      setFormData(initialValues);
    }
  }, [isOpen, initialValues, onDialogClose]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="382px"
        className="w-[29%] p-[1.5rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
          <VisuallyHidden>add model</VisuallyHidden>
        </Dialog.Title>
        <Box className="pb-3">
          <Flex justify="between" align="center">
            <Text_16_600_FFFFFF className="p-0 pt-1 m-0">
              {title}
            </Text_16_600_FFFFFF>
            <Dialog.Close>
              <Button
                className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem] outline-none"
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
          <label className="pb-1 block">
            <Text_12_400_787B83 mb="1">Cluster Name</Text_12_400_787B83>
            <TextInput
              name="name"
              onChange={(e) => handleChange(e.target.name, e.target.value)}
              placeholder="Enter name"
              maxLength={100}
              className="text-[#FFFFFF]"
            />
            {errors.name && (
              <Text className="text-red-500 text-[.7rem]">{errors.name}</Text>
            )}
          </label>
          <label className="pb-1 mt-3 block w-[48%]">
            <Text_12_400_787B83 mb="1">Type</Text_12_400_787B83>
            <SelectInput
              size="2"
              onValueChange={(value) => handleChange("type", value.value)}
              value={formData?.type}
              placeholder="Select type"
              showSearch={false}
              selectItems={options}
              valueClassName={formData?.type ? "uppercase" : ""}
            />
            {errors.type && (
              <Text className="text-red-500 text-[.7rem]">{errors.type}</Text>
            )}
          </label>
          <label className="pb-1 mt-3 block w-[48%]">
            <Text_12_400_787B83 mb="1">Configuration</Text_12_400_787B83>
            <FileInput
              acceptedFileTypes={[".yaml"]}
              maxFiles={1}
              onFilesChange={handleFilesSelected}
            />
            {errors.configuration && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.configuration}
              </Text>
            )}
          </label>
          <label className="pb-1 block">
            <Text_12_400_787B83 mb="1">{""}</Text_12_400_787B83>
            <Flex align="center" justify="start" gap="2" className="mt-5">
              <Checkbox.Root
                className={`w-[0.875rem] h-[0.875rem] border rounded
                    ${formData?.enable_master_node ? "bg-[transparent] border-[#965CDE]" : "border-gray-300"}
                    `}
                checked={formData?.enable_master_node}
                onCheckedChange={(value: any) =>
                  handleCheck("enable_master_node", value)
                }
              >
                <Checkbox.Indicator
                  className={`flex items-center justify-center mt-[-.05rem] bg-[transparent]
                      ${formData?.enable_master_node ? "bg-[transparent] text-[#965CDE]" : "border-gray-300"}
                    `}
                >
                  <CheckIcon />
                </Checkbox.Indicator>
              </Checkbox.Root>
              <Text
                as="div"
                className="text-xs font-light text-[#FFFFFF]"
                weight="bold"
              >
                Deploy to head node
              </Text>
            </Flex>
            {errors.enable_master_node && (
              <Text className="text-red-500 text-[.7rem]">
                {errors.enable_master_node}
              </Text>
            )}
          </label>
        </Box>
        <Flex gap="3" mt="4" justify="center">
          <ButtonInput
            size="1"
            className="h-[1.75rem] w-full"
            onClick={handleSubmit}
          >
            Add Cluster
          </ButtonInput>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default AddClusterPopup;
