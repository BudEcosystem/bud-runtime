import React from 'react';
import { Dialog, Button, Flex, Box } from '@radix-ui/themes';
import { Cross1Icon, UpdateIcon } from '@radix-ui/react-icons';
import { Text_12_400_787B83, Text_16_600_FFFFFF } from '@/components/ui/text';

interface BenchmarkGeneratingProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
}

const BenchmarkGeneratingPopup: React.FC<BenchmarkGeneratingProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
}) => {
  const onCloseDialog = () => {
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={() => {}}>
      <Dialog.Content
        maxWidth="364px"
        className=" p-[1.125rem] bg-[#111113] border-0 shadow-none"
        aria-describedby={undefined}
      >
        <Dialog.Title className="mb-2">
          <Flex justify="between" align="center" mb="1">
            <Flex align="center">
              <UpdateIcon className="w-4 h-4 mr-2" />
              <Text_16_600_FFFFFF>{title}</Text_16_600_FFFFFF>
            </Flex>
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
        </Dialog.Title>
        <Box className="pb-3">
          <Text_12_400_787B83>{description}</Text_12_400_787B83>
        </Box>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default BenchmarkGeneratingPopup;
