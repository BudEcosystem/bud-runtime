// components/DeleteDialog.tsx
import React from "react";
import { Button, Dialog, Flex, VisuallyHidden } from "@radix-ui/themes";
import { Cross1Icon } from "@radix-ui/react-icons";
import { ButtonInput } from "@/components/ui/button";
import { Text_12_400_787B83, Text_16_600_FFFFFF } from "@/components/ui/text";

interface DeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onDelete: () => void;
  itemName: string;
}

const DeleteDialog: React.FC<DeleteDialogProps> = ({
  isOpen,
  onClose,
  onDelete,
  itemName,
}) => {
  return (
    <Dialog.Root open={isOpen}>
      <Dialog.Content
        maxWidth="370px"
        className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title>
          <VisuallyHidden>Delete endpoint</VisuallyHidden>
        </Dialog.Title>
        <Flex justify="between" align="center">
          <Text_16_600_FFFFFF className="p-0 pt-1 m-0">
            Are you sure?
          </Text_16_600_FFFFFF>
          <Dialog.Close onClick={onClose}>
            <Button
              className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem] outline-none"
              size="1"
            >
              <Cross1Icon />
            </Button>
          </Dialog.Close>
        </Flex>
        <Text_12_400_787B83 className="pt-2 mb-6">
          You’re about to delete <b>{itemName}</b> model from the entire
          repository . It will be deleted from the projects as well.
        </Text_12_400_787B83>
        <Flex gap="3" mt="4" justify="center">
          <ButtonInput className="w-full" onClick={onDelete}>
            Delete Model
          </ButtonInput>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default DeleteDialog;
