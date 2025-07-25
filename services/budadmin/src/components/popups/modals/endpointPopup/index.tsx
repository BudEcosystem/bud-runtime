import React, { useEffect, useState } from 'react';
import { Dialog, Button, Text, TextField, Select, Flex, Box, VisuallyHidden } from '@radix-ui/themes';
import { SelectInput, TextInput } from '@/components/ui/input';
import { Text_12_300_44474D } from '@/components/ui/text';


interface EndpointModelProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  projectsOptions: { value: string; label: string }[]; // Options for projects
  clustersOptions: { value: string; label: string }[]; // Options for clusters
  initialValues?: {
    project_id?: string; // Default selected project
    cluster?: string; // Default selected cluster
    workers?: string; // Default selected worker
  };
  onSubmit: (formData: { [key: string]: string }, values) => void;
}


const EndpointModel: React.FC<EndpointModelProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  projectsOptions,
  clustersOptions,
  initialValues = {},
  onSubmit,
}) => {
  // Initialize form data with default values
  const [formData, setFormData] = React.useState<{ [key: string]: any }>();
  const [isDeployButtonEnabled, setIsDeployButtonEnabled] = useState(false);

  const [selectedProject, setSelectedProject] = useState<any>();
  const [selectedCluster, setSelectedCluster] = useState<any>();
  const [selectedWorkers, setSelectedWorkers] = useState<any>(1);

  useEffect(() => {
    setFormData({
      "cluster_id": selectedCluster?.['id'],
      "project_id": selectedProject?.['project']?.['id'],
      "workers": selectedWorkers ? selectedWorkers : 1,
      "cache_enabled": false,
    })
  }, [selectedProject, selectedCluster, selectedWorkers]);

  // Handle form submission
  const handleSubmit = () => {
    onSubmit(formData, initialValues);
  };

  useEffect(() => {
    const isProjectSelected = !!selectedProject?.['project']?.['name'];
    const isClusterSelected = !!selectedCluster?.['name'];
    const isWorkerCountValid = !!selectedWorkers;

    if (isProjectSelected && isClusterSelected && isWorkerCountValid) {
      setIsDeployButtonEnabled(true);
    } else {
      setIsDeployButtonEnabled(false);
    }
  }, [selectedProject, selectedCluster, selectedWorkers]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content maxWidth="370px" className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none" aria-describedby={undefined}>
        <Dialog.Title>
          <VisuallyHidden>add endpoint</VisuallyHidden>
        </Dialog.Title>
        <Flex justify="end" align="center" className='pb-6'>
          {/* <Button className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem] text-[#787B83]" size="1">
            <ArrowLeftIcon />
          </Button> */}
          <Dialog.Close>
            <Button className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem] text-[#787B83]" size="1" >
              Skip
            </Button>
          </Dialog.Close>
        </Flex>
        <Dialog.Title className="text-base block p-0 pt-1 m-0">Add Endpoints to projects</Dialog.Title>
        <Text_12_300_44474D className="text-xs text-[#44474D] pt-2" mb="4">
          Select one or more projects to link with the new model
        </Text_12_300_44474D>
        <Flex direction="row" gap="3" mt="4">
          {/* Project Select */}
          <label className="pb-1 max-w-[32%]" key="project_id">
            <Text as="div" className="text-xs font-normal text-[#787B83]" mb="1" weight="bold">
              Project
            </Text>
            <SelectInput
              size="2"
              value={selectedProject?.['project']['name'] || ''}
              onValueChange={(newValue) => setSelectedProject(newValue)}
              placeholder={`Select project`}
              selectItems={projectsOptions}
              renderItem=""
            />
          </label>
          {/* Cluster Select */}
          <label className="pb-1 max-w-[32%]" key="cluster">
            <Text as="div" className="text-xs font-normal text-[#787B83]" mb="1" weight="bold">
              Cluster
            </Text>

            <SelectInput
              size="2"
              value={selectedCluster?.['name'] || ''}
              onValueChange={(newValue) => setSelectedCluster(newValue)}
              placeholder={`Select cluster`}
              selectItems={clustersOptions}
              renderItem=""
            />

          </label>
          {/* Workers Input */}
          <label className="pb-1 max-w-[32%]" key="workers">
            {/* Workers label */}
            <Text as="div" className="text-xs font-normal text-[#787B83]" mb="1" weight="bold">
              Workers
            </Text>
            {/* Workers input */}
            <TextInput
              name="workers"
              type="number"
              value={selectedWorkers || ''}
              onChange={(e) => setSelectedWorkers(e.target.value)}
              placeholder="No. of workers"
              maxLength={100}
              className="text-[#FFFFFF]"
            />
          </label>
        </Flex>
        {/* Submit button */}
        <Flex gap="3" mt="4" justify="center">
          <Button size="1" className="h-[1.75rem] w-full text-xs font-normal" onClick={handleSubmit} disabled={!isDeployButtonEnabled}>
            Link
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};


export default EndpointModel;