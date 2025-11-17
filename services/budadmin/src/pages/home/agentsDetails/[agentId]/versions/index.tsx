import React from "react";
import { Button, Tag } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_24_600_FFFFFF,
} from "@/components/ui/text";
import { formatDate } from "src/utils/formatDate";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";

interface VersionsTabProps {
  agentData: any;
}

const VersionsTab: React.FC<VersionsTabProps> = ({ agentData }) => {
  // Mock data for current version
  const currentVersion = {
    version: "V1",
    deploymentName: "Deployment name",
    visibility: "Public",
    createdDate: "3rd July, 2024",
    lastUpdated: "7th July, 2024",
  };

  // Mock data for previous versions
  const previousVersions = [
    {
      key: "1",
      version: "V1",
      deploymentName: "Deployment name",
      visibility: "Public",
      createdDate: "3rd July, 2024",
      lastUpdated: "7th July, 2024",
    },
    {
      key: "2",
      version: "V1",
      deploymentName: "Deployment name",
      visibility: "Public",
      createdDate: "3rd July, 2024",
      lastUpdated: "7th July, 2024",
    },
    {
      key: "3",
      version: "V1",
      deploymentName: "Deployment name",
      visibility: "Public",
      createdDate: "3rd July, 2024",
      lastUpdated: "7th July, 2024",
    },
    {
      key: "4",
      version: "V1",
      deploymentName: "Deployment name",
      visibility: "Public",
      createdDate: "3rd July, 2024",
      lastUpdated: "7th July, 2024",
    },
  ];

  const VersionCard = ({
    version,
    deploymentName,
    visibility,
    createdDate,
    lastUpdated,
    showDeploy = false
  }: {
    version: string;
    deploymentName: string;
    visibility: string;
    createdDate: string;
    lastUpdated: string;
    showDeploy?: boolean;
  }) => (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 flex items-center justify-between mb-4">
      <div className="flex items-center gap-6">
        {/* Version Badge */}
        <div className="flex items-center justify-center w-16 h-16 bg-[#1A1A1A] border border-[#2F2F2F] rounded-lg">
          <Text_24_600_FFFFFF>{version}</Text_24_600_FFFFFF>
        </div>

        {/* Version Info */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Text_14_600_EEEEEE>{deploymentName}</Text_14_600_EEEEEE>
            <Tag color="green" className="m-0">
              {visibility}
            </Tag>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11.0833 2.33333H10.5V1.16667C10.5 0.970833 10.3292 0.8 10.1333 0.8C9.9375 0.8 9.76667 0.970833 9.76667 1.16667V2.33333H4.23333V1.16667C4.23333 0.970833 4.0625 0.8 3.86667 0.8C3.67083 0.8 3.5 0.970833 3.5 1.16667V2.33333H2.91667C2.1625 2.33333 1.55 2.94583 1.55 3.7V11.6333C1.55 12.3875 2.1625 13 2.91667 13H11.0833C11.8375 13 12.45 12.3875 12.45 11.6333V3.7C12.45 2.94583 11.8375 2.33333 11.0833 2.33333ZM11.7167 11.6333C11.7167 11.9833 11.4333 12.2667 11.0833 12.2667H2.91667C2.56667 12.2667 2.28333 11.9833 2.28333 11.6333V5.83333H11.7167V11.6333Z" fill="#B3B3B3"/>
              </svg>
              <Text_12_400_B3B3B3>Created Date</Text_12_400_B3B3B3>
              <Text_12_400_B3B3B3 className="text-[#EEEEEE]">{createdDate}</Text_12_400_B3B3B3>
            </div>
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11.0833 2.33333H10.5V1.16667C10.5 0.970833 10.3292 0.8 10.1333 0.8C9.9375 0.8 9.76667 0.970833 9.76667 1.16667V2.33333H4.23333V1.16667C4.23333 0.970833 4.0625 0.8 3.86667 0.8C3.67083 0.8 3.5 0.970833 3.5 1.16667V2.33333H2.91667C2.1625 2.33333 1.55 2.94583 1.55 3.7V11.6333C1.55 12.3875 2.1625 13 2.91667 13H11.0833C11.8375 13 12.45 12.3875 12.45 11.6333V3.7C12.45 2.94583 11.8375 2.33333 11.0833 2.33333ZM11.7167 11.6333C11.7167 11.9833 11.4333 12.2667 11.0833 12.2667H2.91667C2.56667 12.2667 2.28333 11.9833 2.28333 11.6333V5.83333H11.7167V11.6333Z" fill="#B3B3B3"/>
              </svg>
              <Text_12_400_B3B3B3>Last Updated</Text_12_400_B3B3B3>
              <Text_12_400_B3B3B3 className="text-[#EEEEEE]">{lastUpdated}</Text_12_400_B3B3B3>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <Button
          className="bg-transparent border border-[#4D4D4D] text-[#EEEEEE] hover:bg-[#1F1F1F] rounded-md h-[32px] px-4 flex items-center gap-2"
          onClick={() => {}}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M11.0871 1.04488C10.9933 0.951116 10.8661 0.898438 10.7335 0.898438C10.6009 0.898438 10.4737 0.951116 10.38 1.04488L3.44805 7.9768C3.35809 8.06675 3.28612 8.17305 3.23601 8.28998L1.87394 11.4681C1.7934 11.6561 1.83539 11.8741 1.97996 12.0187C2.12453 12.1632 2.34255 12.2052 2.53047 12.1247L5.70863 10.7626C5.82556 10.7125 5.93186 10.6405 6.02182 10.5506L12.9537 3.61866C13.149 3.4234 13.149 3.10681 12.9537 2.91155L11.0871 1.04488ZM4.15515 8.6839L10.7335 2.10554L11.8931 3.2651L5.31471 9.84346L3.91273 10.4443L3.5543 10.0859L4.15515 8.6839Z" fill="#EEEEEE"/>
          </svg>
          Edit
        </Button>
        {showDeploy && (
          <Button
            className="bg-[#965CDE] border-none text-white hover:bg-[#7E4DBD] rounded-md h-[32px] px-4 flex items-center gap-2"
            onClick={() => {}}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12.25 6.41732C12.2503 6.34843 12.2232 6.28199 12.175 6.23232L7.51667 1.57398C7.46591 1.52323 7.39803 1.49414 7.32708 1.49414C7.25614 1.49414 7.18826 1.52323 7.1375 1.57398L6.4875 2.22398C6.38302 2.32846 6.38302 2.49904 6.4875 2.60357L9.93917 6.05482H2.04167C1.8938 6.05482 1.77083 6.17779 1.77083 6.32565V7.30398C1.77083 7.45185 1.8938 7.57482 2.04167 7.57482H9.93917L6.4875 11.0261C6.38302 11.1306 6.38302 11.3011 6.4875 11.4057L7.1375 12.0557C7.18826 12.1064 7.25614 12.1355 7.32708 12.1355C7.39803 12.1355 7.46591 12.1064 7.51667 12.0557L12.175 7.39732C12.2232 7.34765 12.2503 7.28121 12.25 7.21232V6.41732Z" fill="white"/>
            </svg>
            Deploy
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <div className="pb-8 pt-[.5rem]">
      {/* Current Version Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <Text_24_600_FFFFFF>Current Version</Text_24_600_FFFFFF>
          <Button
            className="bg-[#965CDE] border-none text-white hover:bg-[#7E4DBD] rounded-md h-[36px] px-6"
            onClick={() => {}}
          >
            Add Version
          </Button>
        </div>
        <VersionCard {...currentVersion} />
      </div>

      {/* Previous Versions Section */}
      <div>
        <Text_24_600_FFFFFF className="block mb-6">Previous Version</Text_24_600_FFFFFF>
        {previousVersions.map((version) => (
          <VersionCard key={version.key} {...version} showDeploy={true} />
        ))}
      </div>
    </div>
  );
};

export default VersionsTab;
