import { ConfigProvider, Popover, Tooltip } from "antd";
import React from "react";
import CustomPopover from "@/flows/components/customPopover";
import { useDrawer } from "@/hooks/useDrawer";

export enum FormProgressStatus {
  completed = "completed",
  inProgress = "inProgress",
  notCompleted = "notCompleted",
  failed = "failed",
}

export type FormProgressType = {
  status: FormProgressStatus;
  title: string;
  hidden?: boolean;
};

const completed = <li className="flex w-full items-center text-[#965CDE] after:content-[''] after:w-full after:h-0.5 after:border-b after:border-[#965CDE] after:border-2 after:inline-block rounded-[6px] overflow-hidden	"></li>
const notCompleted = <li className="flex w-full items-center after:content-[''] after:w-full after:h-0.5 after:border-b after:border-[#1F1F1F] after:border-2 after:inline-block  rounded-[6px] overflow-hidden	"></li>

function FormProgress() {
  const { step } = useDrawer()

  if (step.progress.length === 0) {
    return null;
  }
  // include either current step or unique steps


  if (step.progress.length === 1) {
    return (
      <div />
    )
  }

  return (
    <ol className="flex items-center w-full h-1 m-0 gap-[.5rem] justify-between cursor-pointer h-[0.1875rem]">
      {step.progress?.filter((item) => !item.hidden).map(({
        status,
        title,
      }, index) => {
        if (status === "completed" || status === "inProgress") {
          return <CustomPopover key={title+index} title={title}>{completed}</CustomPopover>;
        } else {
          return <CustomPopover key={title+index} title={title}>{notCompleted}</CustomPopover>;
        }
      })}
    </ol>
  );
}

export default FormProgress;