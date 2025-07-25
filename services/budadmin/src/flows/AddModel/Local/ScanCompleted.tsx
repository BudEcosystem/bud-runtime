
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3 } from "@/components/ui/text";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd"; // Added Checkbox import
import SelectedModeInfoCard from "src/flows/components/SelectedModeInfoCard";
import { useDeployModel } from "src/stores/useDeployModel";
import { ModelIssue, ScanResult, useModels } from "src/hooks/useModels";
import Tags from "src/flows/components/DrawerTags";
import { capitalize, statusColor } from "@/lib/utils";


export type ScanResultItemProps = {
  icon: string,
  name: string,
  count?: number | string,
  tag?: {
    name: string,
    color: string,
    image: boolean,
  },
  children?: ModelIssue[],
};

function ScanResultItem({ data }: {
  data: ScanResultItemProps
}) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen(!open)}
      className={`px-[1.4rem] border-b-[1px] border-b-[#FFFFFF08] border-t-[1px] border-t-[transparent] hover:border-t-[#757575] hover:border-b-[1px] hover:border-b-[#757575] cursor-pointer
      ${open
          ? "!border-b-[#757575] !border-t-[#757575]"
          : "border-b-[#FFFFFF08] border-t-[transparent] hover:border-t-[#757575] hover:border-b-[#757575]" // Styles when open is false
        }
    `}>
      <div className="flex justify-between items-center py-[.8rem]">
        <div className="flex justify-start items-center">
          {data.icon && (
            <div className="w-[.75rem] mr-[.5rem]">
              <Image
                preview={false}
                src={data.icon}
                alt="Logo"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </div>
          )}
          <Text_12_400_B3B3B3
            className="width-82"
          >{data.name}</Text_12_400_B3B3B3>
          {data.count && (
            <>
              <div className="ml-[1rem]" />
              <Text_12_400_B3B3B3>{data.count}</Text_12_400_B3B3B3>
            </>
          )}
          {data.tag && (
            <>
              <div className="ml-[1rem]" />
              <Tags name={data.tag.name} color={data.tag.color} />
            </>
          )}

        </div>
        {data.children?.length > 0 && (<div className="flex justify-end items-start">
          <div className="w-[0.9375rem] h-[0.9375rem] "
          >
            <Image
              preview={false}
              width={15}
              src="/images/drawer/ChevronUp.png"
              alt="Logo"
              style={{ transform: !open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.3s ease' }}
            />
          </div>
        </div>)}
      </div>
      {open && data.children?.length > 0 && (
        <div className="flex flex-col	gap-[.9rem] justify-between flex-wrap items-center w-full pb-[1rem]">
          {data.children?.map((item, index) => (
            <div
              key={index}
              className="ibm text-[#C7C7C7] text-[0.625rem] bg-[#1F1F1F] rounded-[8px] w-full py-[.75rem] px-[.9rem]">
              {item.title}: <br />
              -Severity: {capitalize(item.severity)}<br />
              -Description: {item.description}<br />
              -Source: {item.source}<br />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ScanCompleted() {
  const { currentWorkflow, getWorkflow } = useDeployModel();
  const { closeDrawer, openDrawer } = useDrawer()
  const { getModel, selectedModel } = useModels();

  useEffect(() => {
    getWorkflow();
  }, []);

  const scanResult: ScanResult = currentWorkflow?.workflow_steps?.security_scan_result || selectedModel?.scan_result;
  const isScanCompleted = currentWorkflow?.workflow_steps?.security_scan_result?.model_id;

  const scanResults: ScanResultItemProps[] = [
    {
      icon: '/images/drawer/meter.png',
      name: 'Status',
      tag: {
        name: capitalize(scanResult?.status) || 'Unknown',
        color: statusColor(scanResult?.status),
        image: false,
      }
    },
    {
      icon: '/images/drawer/alertIcn.png',
      name: 'Scanned Files',
      count: scanResult?.total_scanned_files || `0`,
    },
    // {
    //   icon: '/images/drawer/alertIcn.png',
    //   name: 'Skipped Files',
    //   count: scanResult?.total_skipped_files,
    //   tag: !scanResult?.total_skipped_files && {
    //     name: 'No Skipped Files',
    //     color: '#757575',
    //     image: false,
    //   }
    // },
    {
      icon: '/images/drawer/alertIcn.png',
      name: 'Total Issues',
      count: scanResult?.total_issues > 0 ? scanResult?.total_issues : '',
      tag: !scanResult?.total_issues && {
        name: 'No Issues',
        color: '#757575',
        image: false,
      }
    },
    {
      icon: '/images/drawer/greyWarning.png',
      name: 'Critical',
      count: scanResult?.critical_severity_count > 0 ? scanResult?.critical_severity_count : '',
      children: scanResult?.model_issues?.critical || [],
      tag: !scanResult?.critical_severity_count && {
        name: 'No Issues',
        color: '#757575',
        image: false,
      }
    },
    {
      icon: '/images/drawer/alertIcn.png',
      name: 'High',
      count: scanResult?.high_severity_count > 0 ? scanResult?.high_severity_count : '',
      children: scanResult?.model_issues?.high || [],
      tag: !scanResult?.high_severity_count && {
        name: 'No Issues',
        color: '#757575',
        image: false,
      }
    },
    {
      icon: '/images/drawer/alertIcn.png',
      name: 'Medium',
      count: scanResult?.medium_severity_count > 0 ? scanResult?.medium_severity_count : '',
      children: scanResult?.model_issues?.medium || [],
      tag: !scanResult?.medium_severity_count && {
        name: 'No Issues',
        color: '#757575',
        image: false,
      }
    },
    {
      icon: '/images/drawer/alertIcn.png',
      name: 'Low',
      count: scanResult?.low_severity_count > 0 ? scanResult?.low_severity_count : '',
      children: scanResult?.model_issues?.low || [],
      tag: !scanResult?.low_severity_count && {
        name: 'No Issues',
        color: '#757575',
        image: false,
      }
    },
  ]


  return (
    <BudForm
      data={{
      }}
      onNext={async () => {
        await getModel(selectedModel?.id);
        openDrawer('view-model');
      }}
      nextText="View Model"
    >
      <BudWraperBox>
        <SelectedModeInfoCard />
        <BudDrawerLayout>
          <DrawerTitleCard
            title={isScanCompleted ? "Security Scan Completed" : "Security Scan Result"}
            description={isScanCompleted ? "Looks like the scan is done, below are the results" : `Below are the security scan results of ${selectedModel?.name}`}
            classNames="pt-[1.1rem] pb-[1.2rem]"
          />
          {/* <div className="border-t-[1px] border-t-[#1F1F1F] mt-[1.4rem]"> */}
          <div className="">
            {scanResults.map((item, index) => (
              <ScanResultItem key={index} data={item} />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
