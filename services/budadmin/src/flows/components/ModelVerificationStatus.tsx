import { PrimaryButton } from '@/components/ui/bud/form/Buttons';
import { Text_12_400_757575, Text_12_400_B3B3B3, Text_12_400_EEEEEE, Text_14_400_EEEEEE } from '@/components/ui/text';
import { Image } from 'antd';
import { ChevronRight } from 'lucide-react';
import React, { useContext, useState } from 'react'
import Tags from './DrawerTags';
import { useModels } from 'src/hooks/useModels';
import { SpecificationTableItem, SpecificationTableItemProps } from './SpecificationTableItem';
import { capitalize, getSpecValueWidthOddEven, statusColor } from '@/lib/utils';
import { useDrawer } from 'src/hooks/useDrawer';
import { useDeployModel } from 'src/stores/useDeployModel';
import ComingSoon from '@/components/ui/comingSoon';
import { BudFormContext } from '@/components/ui/bud/context/BudFormContext';
import { PermissionEnum, useUser } from 'src/stores/useUser';

export function PendingIcon() {
    return <svg width="100%" height="100%" viewBox="0 0 24 25" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" clipRule="evenodd" d="M12.0025 4.03125C7.33186 4.03125 3.5293 7.83381 3.5293 12.5035C3.5293 17.1741 7.33186 20.9719 12.0025 20.9719C16.6731 20.9719 20.4709 17.1732 20.4709 12.5035C20.4709 7.83285 16.6722 4.03125 12.0025 4.03125Z" fill="#1F1F1F" />
        <path d="M15.5161 9.09879L15.5152 9.09973L15.5159 9.09967C15.7006 9.08561 15.8843 9.14561 16.0259 9.26561C16.3212 9.52061 16.3531 9.96684 16.099 10.2612V10.2622L11.4509 15.6612C11.3216 15.8112 11.135 15.9003 10.9363 15.9059C10.7385 15.9115 10.5463 15.8337 10.4085 15.6912L7.93261 13.1338C7.66167 12.8553 7.66638 12.41 7.94293 12.1381C8.07699 12.006 8.25794 11.9328 8.44544 11.9347C8.63386 11.9366 8.81293 12.0135 8.94418 12.1475H8.94512L10.8876 14.1538L15.0305 9.34441C15.1533 9.20098 15.3277 9.11286 15.5161 9.09879Z" fill="#757575" />
    </svg>
}

function SuccessIcon() {
    return <svg width="100%" height="100%" viewBox="0 0 24 25" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" clipRule="evenodd" d="M12.0025 4.03125C7.33186 4.03125 3.5293 7.83381 3.5293 12.5035C3.5293 17.1741 7.33186 20.9719 12.0025 20.9719C16.6731 20.9719 20.4709 17.1732 20.4709 12.5035C20.4709 7.83285 16.6722 4.03125 12.0025 4.03125Z" fill="#275B25" fillOpacity="0.25" />
        <path d="M15.5161 9.09879L15.5152 9.09973L15.5159 9.09967C15.7006 9.08561 15.8843 9.14561 16.0259 9.26561C16.3212 9.52061 16.3531 9.96684 16.099 10.2612V10.2622L11.4509 15.6612C11.3216 15.8112 11.135 15.9003 10.9363 15.9059C10.7385 15.9115 10.5463 15.8337 10.4085 15.6912L7.93261 13.1338C7.66167 12.8553 7.66638 12.41 7.94293 12.1381C8.07699 12.006 8.25794 11.9328 8.44544 11.9347C8.63386 11.9366 8.81293 12.0135 8.94418 12.1475H8.94512L10.8876 14.1538L15.0305 9.34441C15.1533 9.20098 15.3277 9.11286 15.5161 9.09879Z" fill="#44C969" />
    </svg>
}

function FailedIcon() {
    return <svg width="100%" height="100%" viewBox="0 0 24 25" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" clipRule="evenodd" d="M12.0015 4.0293C7.33088 4.0293 3.52832 7.83186 3.52832 12.5015C3.52832 17.1722 7.33088 20.9699 12.0015 20.9699C16.6722 20.9699 20.4699 17.1712 20.4699 12.5015C20.4699 7.8309 16.6712 4.0293 12.0015 4.0293Z" fill="#5B2525" fillOpacity="0.25" />
        <path d="M15.7668 15.645L13.1612 13.0026L15.777 10.3603C16.0891 10.0384 16.0686 9.53154 15.7468 9.21965C15.4147 8.91725 14.8814 8.92716 14.5698 9.24897L12.0043 11.8426L9.44861 9.24897C9.13657 8.92716 8.60367 8.91764 8.2716 9.21965C7.93951 9.52204 7.92969 10.0385 8.24134 10.3603L10.8469 13.0026L8.23148 15.645C8.08057 15.8011 8 16.0056 8 16.22C8 16.4344 8.10061 16.6393 8.25152 16.7757C8.40243 16.9219 8.60365 17 8.83513 17C9.05638 17 9.27764 16.9124 9.43877 16.7563L11.994 14.1627L14.5493 16.7563C14.7104 16.9124 14.9214 17 15.1529 17C15.3643 17 15.5656 16.9219 15.7263 16.7757C15.8874 16.6294 15.9778 16.4245 15.988 16.2101C15.9983 16.0056 15.9177 15.8011 15.7668 15.645Z" fill="#C94444" />
    </svg>
}

function SecurityScan() {
    const { isExpandedViewOpen } = useContext(BudFormContext)
    const { openDrawerWithStep } = useDrawer();
    const { selectedModel } = useModels();
    const [seeMore, setSeeMore] = useState(false);
    const { currentWorkflow, startSecurityScan, reset } = useDeployModel();
    const { hasPermission } = useUser()

    const results: SpecificationTableItemProps[] = [
        {
            icon: '/images/drawer/meter.png',
            name: 'Status',
            value: [capitalize(selectedModel?.scan_result?.status || 'pending')],
            tagColor: statusColor(selectedModel?.scan_result?.status || 'pending')
        },
        {
            icon: '/images/drawer/lens.png',
            name: 'Total Issues',
            value: selectedModel?.scan_result?.total_issues || '0',
        },
        {
            icon: '/images/drawer/alertIcn.png',
            name: 'Critical Severity',
            value: selectedModel?.scan_result?.critical_severity_count || '0',
        },
        {
            icon: '/images/drawer/greyWarning.png',
            name: 'High Severity',
            value: selectedModel?.scan_result?.high_severity_count || '0',
        },
        {
            icon: '/images/drawer/greyWarning.png',
            name: 'Medium Severity',
            value: selectedModel?.scan_result?.medium_severity_count || '0',
        },
        {
            icon: '/images/drawer/lens.png',
            name: 'Low Severity',
            value: selectedModel?.scan_result?.low_severity_count || '0',
        },
        // {
        //     icon: '/images/drawer/lens.png',
        //     name: 'Total Scanned Files',
        //     value: selectedModel?.scan_result?.total_scanned_files || '0',
        // },
        // {
        //     icon: '/images/drawer/lens.png',
        //     name: 'Total Skipped Files',
        //     value: selectedModel?.scan_result?.total_skipped_files || '0',
        // }
    ]
    console.log('currentWorkflow',currentWorkflow)

    if (!selectedModel?.scan_result) {
        return <div className="w-full">
            <div className="px-[0.7rem] mb-[1.2rem] pt-[.3rem]">
                <Text_12_400_757575 className="mt-[.55rem] pr-[3rem]">Scan your model for security vulnerabilities before you start deploying it.</Text_12_400_757575>
            </div>
            <div className="flex justify-end items-end px-[0.7rem] pt-[2.6rem] pb-[.3rem]">
                {(hasPermission(PermissionEnum.ModelManage) && (currentWorkflow?.workflow_steps?.model_security_scan_events?.status != "PENDING") || !selectedModel.scan_verified) &&
                    <PrimaryButton
                        permission={hasPermission(PermissionEnum.ModelManage)}
                        disabled={isExpandedViewOpen}
                        onClick={async () => {
                            if (isExpandedViewOpen) return;

                            const result = await startSecurityScan();
                            if (result) {
                                openDrawerWithStep('security-scan-status')
                            }
                        }}
                        text="Scan the model"
                    >
                    </PrimaryButton>
                }
            </div>
        </div>
    }


    return (
        <div className="w-full">
            <div className="px-[0.7rem] mb-[1.2rem]">
                <Text_12_400_757575 className="mt-[.55rem]">Model has been scanned and below are the results.</Text_12_400_757575>
            </div>
            <div className="px-[0.7rem] flex justify-start items-center flex-wrap gap-x-[1.1rem] gap-y-[.95rem] w-[100%] pb-[1.05rem]">
                <div className="pt-[.8rem] flex justify-between items-center flex-wrap gap-y-[1.5rem]">
                    {results
                        // ?.splice(0,seeMore ? results.length : 4)
                        ?.map((item, index) => (
                            <SpecificationTableItem key={index} item={item} />
                        ))}
                </div>
            </div>
            {/* {!seeMore && <div className="flex justify-end items-center mb-[1.2rem] "
                onClick={() => setSeeMore(!seeMore)}
            >
                <div className="items-center text-[0.75rem] font-[400] cursor-pointer text-[#EEEEEE] hover:text-[#EEEEEE] flex whitespace-nowrap">
                    See {seeMore ? 'Less' : 'More'}
                    <ChevronRight className="h-[1rem] text-[#EEEEEE]" />
                </div>
            </div>} */}
            {<div className="flex justify-end items-center mb-[1.2rem] "
                onClick={async () => {
                    if (isExpandedViewOpen) return;

                    reset();
                    openDrawerWithStep('model-scan-result')
                }}
            >
                <div className="items-center text-[0.75rem] font-[400] cursor-pointer text-[#EEEEEE] hover:text-[#EEEEEE] flex whitespace-nowrap">
                    See More
                    <ChevronRight className="h-[1rem] text-[#EEEEEE]" />
                </div>
            </div>}
        </div>
    );
}


function ModelEvals({ item }: { item?: any }) {
    const evalResult = ['IFEval', 'IFEval', 'IFEval', 'BBH', 'BBH', 'BBH', 'Model', 'Model', 'Model'];
    return (
        <div className="w-full relative">
            <div className="px-[0.7rem] mb-[1.2rem]">
                {/* <Text_14_400_EEEEEE>Model Evaluations</Text_14_400_EEEEEE> */}
                <Text_12_400_757575 className="mt-[.55rem]">Evaluations that have been ran.</Text_12_400_757575>
            </div>
            <div className="grid grid-cols-3 gap-[.2rem] gap-y-[.9rem] justify-start px-[0.7rem] mb-[1rem] pt-[.2rem] w-[57%]">
                {evalResult.map((item, index) => (
                    <div
                        key={index}
                        className="inline-block w-[8rem] text-left">
                        <Text_12_400_EEEEEE key={index}>{item}</Text_12_400_EEEEEE>
                    </div>
                ))}
            </div>
        </div>
    );
}

function Scan({ item }: { item?: any }) {
    const { selectedModel } = useModels();
    return (
        <div className="w-full">
            <div className="px-[0.7rem] mb-[1.2rem]">
                <Text_12_400_757575 className="mt-[.55rem]">{
                    selectedModel?.bud_verified ? 'Model has been verified by Bud.' : 'Model has not been verified by Bud.'
                }</Text_12_400_757575>
            </div>

        </div>
    );
}

export default function ModelVerificationStatus({ item }: { item?: any }) {
    const [activeTab, setActiveTab] = useState("");
    const { selectedModel } = useModels();

    const tabs = [
        {
            name: 'Bud Verified',
            icon: selectedModel?.bud_verified ? SuccessIcon : PendingIcon,
            description: 'This model has been verified by Bud.',
            content: <Scan />
        },
        selectedModel?.provider_type !== "cloud_model" ? {
            name: 'Security Scan',
            icon: selectedModel?.scan_result ? selectedModel.scan_verified ? SuccessIcon : FailedIcon : PendingIcon,
            description: 'This model has been scanned for security vulnerabilities.',
            content: <SecurityScan />
        } : undefined,
        {
            name: 'Evaluations',
            icon: selectedModel?.eval_result ? selectedModel.eval_verified ? SuccessIcon : FailedIcon : PendingIcon,
            description: 'This model has been evaluated.',
            content: <ModelEvals />
        },
    ]?.filter(Boolean);

    const tabContent = tabs.find(tab => tab.name === activeTab);

    return (
        <div
            className={`statuses mb-[1.05rem] width-352 relative ${activeTab ? 'hovered' : ''}`}
            onMouseLeave={() => setActiveTab("")}
        >
            <div
                className="absolute-div absolute z-[1250] flex-col justify-start left-[-3%] top-[-0.35rem] mt-[0rem] pt-[2.75rem] rounded-[8px] bg-[#1F1F1F]  w-full min-h-[13.25rem] overflow-hidden shadow-sm shadow-[0_1px_2px_0_#4D4D4D]"
            >
                {tabContent?.name == 'Evaluations' && (
                    <ComingSoon />
                )}
                {tabContent?.content}
            </div>
            <div className="flex justify-start items-center gap-[.45rem] !relative z-[1300]">
                {/* Dropdown triggers */}
                {tabs.map((tab, index) => (
                    <div
                        key={index}
                        className="flex justify-start items-center px-[.25rem] py-[.25rem] rounded-[8px] cursor-pointer hover:bg-[#161616]"
                        style={{ background: activeTab === tab.name ? '#161616' : '' }}
                        onMouseEnter={() => setActiveTab(tab.name)}
                    >
                        <div className="w-[1.25rem] h-[1.25rem] mr-[.55rem] flex justify-start items-center">
                            <tab.icon />
                        </div>
                        <Text_12_400_EEEEEE className="text-nowrap">{tab.name}</Text_12_400_EEEEEE>
                    </div>
                ))}
            </div>
        </div>

    );
}
