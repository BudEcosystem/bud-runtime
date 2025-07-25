import React, { useCallback, useEffect, useState } from 'react';
import { Dialog, Button, Text, TextField, Flex, Box, VisuallyHidden } from '@radix-ui/themes';
import { Cross1Icon } from '@radix-ui/react-icons';
import { TextAreaInput, TextInput } from '@/components/ui/input';
import { Text_12_300_44474D, Text_12_400_787B83, Text_16_600_FFFFFF } from '@/components/ui/text';

interface EditProjectsPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: { name?: string; description?: string }; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string }) => void;
}

interface FormData {
  name?: string;
  description?: string;
  [key: string]: string | undefined;
}

const EditProjectsPopup: React.FC<EditProjectsPopupProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues = { name: '', description: '' },
  onSubmit,
}) => {
  const [formData, setFormData] = useState<FormData>({ name: '', description: '' });
  const [initialFormData, setInitialFormData] = useState<FormData>({ name: '', description: '' });
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: initialValues.name || '',
        description: initialValues.description || '',
      });
      setIsDirty(false);
      setInitialFormData({
        name: initialValues.name,
        description: initialValues.description,
      })
    }
  }, [isOpen, initialValues]);
  useEffect(() => {
    const hasChanges = JSON.stringify(formData) !== JSON.stringify(initialFormData);
    setIsDirty(hasChanges);
  }, [formData, initialFormData]);

  const handleChange = (e: { target: { name: string; value: string } }) => {
    const { name, value } = e.target;
    const newErrors = { ...errors };
    if (name === "name" && value.trim() === "") {
      newErrors.name = "Project name is required";
    } else if (name === "description" && value.trim().split(' ').length > 50) {
      newErrors.description = "Description cannot exceed 50 words";
    } else {
      delete newErrors[name];
    }
    setFormData((prevData) => ({
      ...prevData,
      [name]: value,
    }));
    setErrors(newErrors);
  };
  const getEditedFields = () => {
    const editedFields: FormData = {};
    for (const key in formData) {
      if (formData[key] !== initialValues[key]) {
        editedFields[key] = formData[key];
      }
    }
    return editedFields;
  };
  const handleSubmit = () => {
    const { name, description } = formData;
    const newErrors = { ...errors };
    if (!name) {
      newErrors.name = "Project name is required";
    }
    if (!description) {
      newErrors.description = "Description is required";
    } else if (description.trim().split(' ').length > 50) {
      newErrors.description = "Description cannot exceed 50 words";
    }
    setErrors(newErrors);
    if (Object.keys(newErrors).length === 0) {
      const editedFields = getEditedFields();
      if (Object.keys(editedFields).length > 0) {
        onSubmit(editedFields);
      }
    }
  };

  const onDialogClose = useCallback(() => {
    setFormData(initialValues);
    setErrors({});
    setIsDirty(false);
  }, [setFormData, initialValues, setErrors]);

  useEffect(() => {
    if (!isOpen) {
      onDialogClose();
    }
  }, [isOpen, onDialogClose]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content maxWidth="370px" className="w-[29%] p-[1.5rem] bg-[#111113] border-0 shadow-none" aria-describedby={undefined}>
        <Dialog.Title>
          <VisuallyHidden>edit project</VisuallyHidden>
        </Dialog.Title>
        <Box className='pb-3'>
          <Flex justify="between" align="center">
            <Text_16_600_FFFFFF className="p-0 pt-1 m-0">{title}</Text_16_600_FFFFFF>
            <Dialog.Close>
              <Button className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem]" size="1">
                <Cross1Icon className='text-[#787B83]' />
              </Button>
            </Dialog.Close>
          </Flex>
          <Text_12_300_44474D className="pt-2" mb="3">
            {description}
          </Text_12_300_44474D>
        </Box>
        <Box>
          <label className="pb-1 block">
            <Text_12_400_787B83 className="pb-1">
              Project Name
            </Text_12_400_787B83>
            <TextInput
              textFieldSlot=""
              name="name"
              value={formData.name || ''}
              onChange={handleChange}
              placeholder="Enter name"
              maxLength={50}
              className="text-[#FFFFFF]"
            />
            {errors.name && <Text className="text-red-500 text-[.7rem]">{errors.name}</Text>}
          </label>
          <label className="pb-1 mt-3 block">
            <Text_12_400_787B83 className="pb-1">
              Description (Maximum 50 words)
            </Text_12_400_787B83>
            <TextAreaInput
              name="description"
              value={formData.description || ''}
              className="!min-h-[90px] text-[#FFFFFF] customPlaceholder"
              onChange={handleChange}
              placeholder="Enter description here"
              maxLength={200} // Assuming 50 words can be approximated to 200 characters
            />
            {errors.description && <Text className="text-red-500 text-[.7rem]">{errors.description}</Text>}
          </label>
        </Box>

        <Flex gap="3" mt="4" justify="center">
          <Button size="1" className="h-[1.75rem] w-full text-xs font-normal" onClick={handleSubmit} disabled={!isDirty}>
            Update Project
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default EditProjectsPopup;
