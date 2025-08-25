import React, { useEffect } from "react";
import {
  Dialog,
  Button,
  Text,
  TextField,
  Flex,
  VisuallyHidden,
  Box,
  Radio,
} from "@radix-ui/themes";
import { Cross1Icon, RadiobuttonIcon } from "@radix-ui/react-icons";
import { Field, SelectFieldType } from "./types"; // Import the Field type
import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_12_400_FFFFFF,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import {
  SelectCustomInput,
  SelectInput,
  TextInput,
} from "@/components/ui/input";
import { ButtonInput } from "@/components/ui/button";
import { FileSliders } from "lucide-react";

interface CommonModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  fields: Field[];
  initialValues?: { [key: string]: string }; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string }) => void;
}

// Example data structures
const textFields = [
  { name: "name", label: "Name" },
  { name: "email", label: "Email" },
  // Add more fields as needed
];

const selectFields = [
  { name: "role", label: "Role", options: ["Admin", "User"] },
  {
    name: "provider",
    label: "Provider",
    options: ["Provider 1", "Provider 2"],
  },

  // Add more fields as needed
];

const CommonModal: React.FC<CommonModalProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  fields,
  initialValues = {}, // Default to empty object
  onSubmit,
}) => {
  const [formData, setFormData] = React.useState<{ [key: string]: string }>({});
  const [modelType, setModelType] = React.useState<string>("bud-serve");
  const provider = ["provider1", "provider2"];
  const modelName = ["OpenAI", "Together.ai"];
  const [editFormData, setEditFormData] = React.useState<{
    [key: string]: string;
  }>({});
  const cloudFields: Field[] = [
    {
      type: "select",
      name: "provider",
      label: "Provider",
      options: provider,
      search: false,
    },
    { type: "text", name: "model", label: "Model Name" },
  ];
  const data = {
    light: { label: "Light" },
    dark: { label: "Dark" },
  };
  const [value, setValue] = React.useState("light");

  useEffect(() => {
    if (isOpen) {
      setFormData(initialValues); // Set form data to initial values when modal is opened
      setEditFormData({}); // Reset editFormData
    }
  }, [isOpen, initialValues]);

  const onDialogClose = () => {
    setFormData({}); // Set form data to initial values when modal is opened
    setEditFormData({});
    setModelType("bud-serve");
  };
  useEffect(() => {
    if (!isOpen) {
      onDialogClose();
    }
  }, [isOpen]);
  const handleChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (initialValues[name] !== value) {
      handleEditChange(name, value);
    } else {
      handleEditChange(name, null); // Remove from editFormData if value is same as initial
    }
  };

  const handleEditChange = (name: string, value: string | null) => {
    setEditFormData((prev) => {
      if (value === null) {
        const { [name]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [name]: value };
    });
  };

  const handleSubmit = () => {
    onSubmit(Object.keys(editFormData).length ? editFormData : formData);
  };

  const isFormValid = () => {
    if (modelType === "bud-serve") {
      for (let field of [...textFields, ...selectFields]) {
        if (!formData[field.name]) {
          return false;
        }
      }
    } else if (modelType === "cloud") {
      if (!formData["provider"] || !formData["name"]) {
        return false;
      }
    }
    return true;
  };

  const textFields = fields.filter((field) => field.type === "text");

  // Filter fields to get only SelectFieldType
  const selectFields: SelectFieldType[] = fields.filter(
    (field): field is SelectFieldType => field.type === "select",
  );
  const cloudSelectFields = cloudFields.filter(
    (field) => field.type === "select",
  );
  const editFields = fields.filter(
    (field) => field.name === "name" || field.name === "uri",
  );
  const nonEditFields = fields.filter(
    (field) => field.name !== "name" && field.name !== "uri",
  );
  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="370px"
        className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
          <VisuallyHidden>add model</VisuallyHidden>
        </Dialog.Title>
        <Flex justify="between" align="center">
          <Text_16_600_FFFFFF className="p-0 m-0">{title}</Text_16_600_FFFFFF>
          <Dialog.Close>
            <Button
              className="m-0 p-0 bg-[transparent] h-[1.1rem]T outline-none"
              size="1"
            >
              <Cross1Icon />
            </Button>
          </Dialog.Close>
        </Flex>
        <Text_12_300_44474D className="pt-[.2rem] mb-4">
          {description}
        </Text_12_300_44474D>
        {!Object.keys(initialValues).length && (
          <Flex gap={"3"} mb={"4"}>
            <Flex align="center">
              <Radio
                id="bud"
                variant="soft"
                name="model"
                value="bud-serve"
                defaultChecked
                className="accent-[#965CDE] mr-1"
                onChange={(e) => {
                  setModelType(e.target.value);
                }}
              />
              <div>
                <Text_12_400_FFFFFF>Bud Serve</Text_12_400_FFFFFF>
              </div>
            </Flex>
            <Flex align="center">
              <Radio
                id="cloud"
                variant="soft"
                name="model"
                value="cloud"
                className="accent-[#965CDE] mr-1"
                onChange={(e) => {
                  setModelType(e.target.value);
                }}
              />
              <div>
                <Text_12_400_FFFFFF>Cloud Providers</Text_12_400_FFFFFF>
              </div>
            </Flex>
          </Flex>
        )}

        {Object.keys(initialValues).length ? (
          <>
            <Flex gap="3" justify="between" className="flex-wrap">
              {nonEditFields.map((field) => {
                let order = {
                  author: "1",
                  source: "2",
                  modality: "3",
                  type: "4",
                };
                return (
                  <div
                    className="pb-1 w-[40%]"
                    key={field.name}
                    style={{ order: order[field.name] }}
                  >
                    <Text_12_400_787B83 mb="1">
                      {field.label}
                    </Text_12_400_787B83>
                    <Text
                      as="div"
                      className="text-xs font-light text-[#6A6E76]"
                      mb="1"
                      weight="bold"
                    >
                      {initialValues.model[field.name]}
                    </Text>
                  </div>
                );
              })}
            </Flex>
            <Flex direction="column" gap="3" mt="4">
              {editFields.map((field) => {
                let order = {
                  name: "1",
                  uri: "2",
                };
                return (
                  <div
                    className="pb-1"
                    key={field.name}
                    style={{ order: order[field.name] }}
                  >
                    <Text_12_400_787B83 mb="1">
                      {field.label}
                    </Text_12_400_787B83>
                    <TextInput
                      textFieldSlot=""
                      name={field.name}
                      onChange={(e) => handleChange(field.name, e.target.value)}
                      placeholder={`Enter ${field.label.toLowerCase()}`}
                      className="text-[#FFFFFF]"
                    />
                  </div>
                );
              })}
            </Flex>
            <Flex gap="3" mt="4" justify="center">
              <ButtonInput
                className="w-full"
                onClick={handleSubmit}
                disabled={Object.keys(editFormData).length < 1}
              >
                Update Model
              </ButtonInput>
            </Flex>
          </>
        ) : (
          <>
            {modelType === "bud-serve" ? (
              <>
                <Flex direction="column" gap="3">
                  {textFields.map((field) => (
                    <div className="pb-1" key={field.name}>
                      <Text_12_400_787B83 mb="1">
                        {field.label}
                        <span className="text-[red]"> *</span>
                      </Text_12_400_787B83>
                      <TextInput
                        textFieldSlot=""
                        name={field.name}
                        value={formData[field.name] || ""}
                        onChange={(e) =>
                          handleChange(field.name, e.target.value)
                        }
                        placeholder={field.placeHolder}
                        maxLength={100}
                        className="text-[#FFFFFF]"
                      />
                    </div>
                  ))}
                </Flex>
                <Flex direction="row" gap="2" mt="4" justify="start">
                  {selectFields.map((field) => (
                    <div className="pb-1 w-[33%]" key={field.name}>
                      <Text_12_400_787B83 mb="1" className="">
                        {field.label}
                        <span className="text-[red]"> *</span>
                      </Text_12_400_787B83>
                      <SelectCustomInput
                        size="2"
                        value={formData[field.name] || ""}
                        onValueChange={(newValue: string) =>
                          handleChange(field.name, newValue)
                        }
                        showSearch={field?.search}
                        placeholder={`Select ${field.label.toLowerCase()}`}
                        selectItems={field["options"]}
                        renderItem=""
                      />
                    </div>
                  ))}
                </Flex>
              </>
            ) : (
              <>
                <Flex direction="column" gap="2" mt="4" justify="start">
                  {cloudSelectFields.map((field) => (
                    <div className="pb-1" key={field.name}>
                      <Text_12_400_787B83 mb="1">
                        Provider
                        <span className="text-[red]"> *</span>
                      </Text_12_400_787B83>
                      <SelectCustomInput
                        size="2"
                        value={formData["provider"] || ""}
                        onValueChange={(newValue) =>
                          handleChange("provider", newValue)
                        }
                        placeholder={`Select provider`}
                        showSearch={field.search}
                        selectItems={[
                          "together.ai",
                          "Bud Ecosystem",
                          "OpenAI",
                          "Bud Ecosystem",
                        ]}
                        renderItem=""
                      />
                    </div>
                  ))}
                </Flex>
                <Flex direction="column" gap="3" mt="4">
                  <div className="pb-1">
                    <Text_12_400_787B83 mb="1">
                      Model Name
                      <span className="text-[red]"> *</span>
                    </Text_12_400_787B83>
                    <TextInput
                      textFieldSlot=""
                      name={"name"}
                      value={formData["name"] || ""}
                      onChange={(e) => handleChange("name", e.target.value)}
                      placeholder={`Enter Model Name`}
                      maxLength={100}
                      className="text-[#FFFFFF]"
                    />
                  </div>
                </Flex>
              </>
            )}

            <Flex gap="3" mt="4" justify="center">
              <ButtonInput
                size="1"
                className="w-full"
                onClick={handleSubmit}
                // disabled={!isFormValid()}
              >
                Add Model
              </ButtonInput>
            </Flex>
          </>
        )}
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default CommonModal;
