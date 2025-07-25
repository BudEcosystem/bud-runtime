// components/DeleteDialog.tsx
import React from 'react';
import {
  Button,
  Dialog,
  Flex,
} from "@radix-ui/themes";
import { Cross1Icon } from '@radix-ui/react-icons';

interface DeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onDelete: () => void;
  itemName: string;
  itemHeadding: string;
  itemDescription: string;
  itemButtonText: string;
}

const DeleteDialog: React.FC<DeleteDialogProps> = ({ isOpen, onClose, onDelete, itemName, itemHeadding, itemDescription, itemButtonText }) => {
  return (
    <Dialog.Root open={isOpen}>
      <Dialog.Content maxWidth="370px" className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none">
        <Flex justify="between" align="center">
          <Dialog.Title className="text-base block p-0 pt-1 m-0 font-semibold">{itemHeadding}</Dialog.Title>
          <Dialog.Close onClick={onClose}>
            <Button className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem]" size="1">
              <Cross1Icon className='text-[#787B83]'/>
            </Button>
          </Dialog.Close>
        </Flex>
        <Dialog.Description className="text-xs text-[#787B83] pt-2 font-normal" mb="4">
          {itemDescription}  
        </Dialog.Description>
        <Flex gap="3" mt="4" justify="center">
          <Button size="1" className="h-[1.75rem] w-full text-xs font-normal" onClick={onDelete}>{itemButtonText}</Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default DeleteDialog;
