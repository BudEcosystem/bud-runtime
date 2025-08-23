import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";
import { successToast, errorToast } from "@/components/toast";
import { Image } from "antd";
import { formatDate } from "@/utils/formatDate";
import CustomPopover from "@/flows/components/customPopover";
import CustomDropDown from "../components/CustomDropDown";
import BudStepAlert from "../components/BudStepAlert";

interface ApiKey {
  id: string;
  name: string;
  project: {
    id: string;
    name: string;
  };
  expiry: string;
  created_at: string;
  last_used_at: string;
  is_active: boolean;
  status: "active" | "revoked" | "expired";
  key?: string;
}

export default function ViewApiKey() {
  const [showConfirm, setShowConfirm] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const { closeDrawer, openDrawer } = useDrawer();
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [copyText, setCopiedText] = useState<string>("Copy");

  useEffect(() => {
    // Get the selected API key from localStorage (set when row is clicked)
    const storedKey = localStorage.getItem("selected_api_key");
    if (storedKey) {
      const keyData = JSON.parse(storedKey);
      setSelectedApiKey(keyData);
      // In a real implementation, you might need to fetch the actual key value
      // For now, we'll use a placeholder
      setApiKeyValue(keyData.key || "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");
    }
  }, []);

  const handleCopy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopiedText("Copied");
      })
      .catch(() => {
        setCopiedText("Failed to copy");
      });
  };

  useEffect(() => {
    if (copyText !== "Copy") {
      const timer = setTimeout(() => {
        setCopiedText("Copy");
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [copyText]);

  if (!selectedApiKey) {
    return null;
  }

  const firstLineText = `Are you sure you want to delete this API key?`
  const secondLineText = `You are about to delete ${selectedApiKey?.name}`

  return (
    <BudForm data={{}}>
      <BudWraperBox>
        {showConfirm && <BudDrawerLayout>
          <BudStepAlert
            type="warning"
            title={firstLineText}
            description={secondLineText}
            confirmText='Delete API Key'
            cancelText='Cancel'
            confirmAction={async () => {
              try {
                await AppRequest.Delete(`/credentials/${selectedApiKey?.id}`);
                successToast('API key deleted successfully');
                closeDrawer();
              } catch (error) {
                errorToast('Failed to delete API key');
              } finally {
                setShowConfirm(false);
              }
            }}
            cancelAction={() => {
              setShowConfirm(false)
            }}
          />
        </BudDrawerLayout>}
        <BudDrawerLayout>
          <div className="px-[1.4rem] pb-[.9rem] rounded-ss-lg rounded-se-lg pt-[1.1rem] border-b-[.5px] border-b-[#1F1F1F] relative">
            <div className="flex justify-between align-center">
              <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0">
                {selectedApiKey?.name}
              </Text_14_400_EEEEEE>
            </div>
            <Text_12_400_757575 className="pt-[.55rem] leading-[1.05rem]">
              API Key Details
            </Text_12_400_757575>
            <div className="absolute right-[.5rem] top-[.5rem]">
              <CustomDropDown
                buttonContent={
                  <div className="px-[.3rem] my-[0] py-[0.02rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/threeDots.png"
                      alt="info"
                      style={{ width: '0.1125rem', height: '.6rem' }}
                    />
                  </div>
                }
                items={
                  [
                    {
                      key: '1',
                      label: 'Edit',
                      onClick: () => {
                        localStorage.setItem('selected_api_key', JSON.stringify(selectedApiKey));
                        openDrawer('edit-api-key');
                      }
                    },
                    {
                      key: '2',
                      label: 'Delete',
                      onClick: () => {
                        setShowConfirm(true)
                      }
                    },
                  ]
                }
              />
            </div>
          </div>
          <div className="px-[1.4rem] pt-[1.4rem] border-b-[1px] border-b-[#1F1F1F]">
            <div className="flex justify-between pt-[1rem] flex-wrap items-center pb-[1.2rem] gap-[1.2rem]">
              {/* API Key */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/key.png"
                      alt="key"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Key</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  {showKey ? (
                    <Text_12_400_EEEEEE className="leading-[100%] !leading-[0.875rem] max-w-[90%] truncate">
                      {apiKeyValue}
                    </Text_12_400_EEEEEE>
                  ) : (
                    <Text_10_400_EEEEEE className="leading-[0.875rem] max-w-[90%] truncate">
                      {apiKeyValue?.replace(/./g, "⏺")}
                    </Text_10_400_EEEEEE>
                  )}
                  <div className="flex justify-end items-center relative">
                    <button
                      onClick={() => setShowKey(!showKey)}
                      className="ml-[.5rem]"
                    >
                      {showKey ? (
                        <EyeOutlined className="text-[#B3B3B3]" />
                      ) : (
                        <EyeInvisibleOutlined className="text-[#B3B3B3]" />
                      )}
                    </button>
                    <CustomPopover title={copyText} contentClassNames="py-[.3rem]">
                      <div
                        className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center ml-[.4rem] cursor-pointer hover:bg-[#1F1F1F]"
                        onClick={() => handleCopy(apiKeyValue)}
                      >
                        <Image
                          preview={false}
                          src="/images/drawer/Copy.png"
                          alt="copy"
                          style={{ height: ".75rem" }}
                        />
                      </div>
                    </CustomPopover>
                  </div>
                </div>
              </div>

              {/* Project Name */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/note.png"
                      alt="project"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Project name</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem] w-[280px] truncate">
                    {selectedApiKey?.project?.name || "N/A"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>

              {/* Created Date */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/calander.png"
                      alt="created"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Created</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem] w-[280px] truncate">
                    {selectedApiKey?.created_at
                      ? formatDate(selectedApiKey.created_at)
                      : "--"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>

              {/* Expiry Date */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/calander.png"
                      alt="expiry"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Expiry Date</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem] w-[280px] truncate">
                    {selectedApiKey?.expiry
                      ? formatDate(selectedApiKey.expiry)
                      : "Never"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>

              {/* Last Used */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/calander.png"
                      alt="last used"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Last Used</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem] w-[280px] truncate">
                    {selectedApiKey?.last_used_at
                      ? formatDate(selectedApiKey.last_used_at)
                      : "--"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>

              {/* Status */}
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className="flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/note.png"
                      alt="status"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Status</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE
                    className="leading-[.875rem] w-[280px] truncate"
                    style={{
                      color:
                        selectedApiKey?.status === "active"
                          ? "#479D5F"
                          : selectedApiKey?.status === "expired"
                            ? "#D1B854"
                            : "#EC7575",
                    }}
                  >
                    {selectedApiKey?.status
                      ? selectedApiKey.status.charAt(0).toUpperCase() +
                      selectedApiKey.status.slice(1)
                      : "--"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
