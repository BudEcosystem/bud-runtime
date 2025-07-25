
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { use, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { ModelNameInput, NameIconInput } from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import { isValidModelName } from "@/lib/utils";
import CustomSelect from "../components/CustomSelect";


export default function HardwareSpecifications() {
  const { openDrawerWithStep } = useDrawer()
  const { currentWorkflow, updateModelDetailsLocal, updateCredentialsLocal, localModelDetails, deleteWorkflow } = useDeployModel();
  const { values, form } = useContext(BudFormContext);

  const statusOptions = [
    {
      value: 'value 1',
      label: 'value 1',
    },
    {
      value: 'value 2',
      label: 'value 2',
    },

  ]

  return (
    <BudForm
      data={localModelDetails}
      onBack={async () => {
        openDrawerWithStep('select-model-for-evaluation')
      }}

      onNext={async () => {
        openDrawerWithStep('simulation-details')
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={'Hardware Specifications'}
            description="Description for Model Quantisation"
          />
          <DrawerCard classNames="">

            <TextInput
              name="nodel"
              label={'Nodel'}
              placeholder={'Enter number nodes'}
              rules={[{message: 'Please enter number nodes' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[1.25rem]"
              infoText={'Enter number nodes'}
            />

            <TextInput
              name="memory"
              label={'Memory'}
              placeholder={'Enter memory in GBs'}
              rules={[{ message: 'Please enter memory in GBs' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[.45rem]"
              infoText={'Enter memory in GBs'}
            />

          </DrawerCard>
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={'Advanced Settings'}
            description="Description for Advanced Settings"
          />
          <DrawerCard classNames="">

            <TextInput
              name="FLOPs"
              label={'FLOPs'}
              placeholder={'Enter number nodes'}
              rules={[{message: 'Please enter number nodes' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[1.25rem]"
              infoText={'Enter number nodes'}
            />

            <TextInput
              name="MemoryBandwidth"
              label={'Memory Bandwidth'}
              placeholder={'Enter Memory Bandwidth'}
              rules={[{ message: 'Please enter Memory Bandwidth' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[1.25rem]"
              infoText={'Enter Memory Bandwidth'}
            />
            
            <TextInput
              name="ICNBandwidth"
              label={'ICN Bandwidth'}
              placeholder={'Enter ICN Bandwidth'}
              rules={[{ message: 'Please enter ICN Bandwidth' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[.45rem]"
              infoText={'Enter ICN Bandwidth'}
            />

          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
