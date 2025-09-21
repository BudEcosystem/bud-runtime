import React, { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  Button,
  Text,
  Flex,
  Box,
  VisuallyHidden,
} from "@radix-ui/themes";
import { Cross1Icon } from "@radix-ui/react-icons";
import { FileInput, SelectInput, TextInput } from "@/components/ui/input";
import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";

interface EditClusterPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: { name?: string; type?: string; configuration?: File[] };
  onSubmit: (formData: { [key: string]: string | File[] }) => void;
}

interface FormData {
  name?: string;
  type?: string;
  configuration?: File[];
  [key: string]: string | File[] | undefined;
}

interface FormErrors {
  name?: string;
  type?: string;
  configuration?: string;
}

const EditClusterPopup: React.FC<EditClusterPopupProps> = ({
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
  const [isNameEdited, setIsNameEdited] = useState(false);

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

    if (name === "name") {
      setIsNameEdited(true);
    }
  };

  const isFormValid = () => {
    return isNameEdited && formData.name && !errors.name;
  };

  const handleSubmit = () => {
    let data = { name: formData.name };
    if (isFormValid()) {
      onSubmit(data);
    }
  };

  const onDialogClose = useCallback(() => {
    setErrors({});
    setFormData(initialValues);
    setIsNameEdited(false);
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
          <VisuallyHidden>edit cluster</VisuallyHidden>
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
              value={formData.name || ""}
              placeholder="Enter cluster name"
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
              value={formData?.type}
              placeholder="Select type"
              selectItems={options}
              disabled
              valueClassName={formData?.type ? "uppercase" : ""}
            />
          </label>
        </Box>
        <Flex gap="3" mt="4" justify="center">
          <ButtonInput
            size="1"
            className="h-[1.75rem] w-full"
            onClick={handleSubmit}
            disabled={!isFormValid()}
          >
            Update Cluster
          </ButtonInput>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default EditClusterPopup;
