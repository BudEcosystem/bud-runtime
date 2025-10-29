import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_EEEEEE,
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import { useDrawer } from "src/hooks/useDrawer";
import { Image, notification, Table } from "antd";
import { assetBaseUrl } from "@/components/environment";
import { formatDate } from "src/utils/formatDate";
import Tags from "src/flows/components/DrawerTags";
import CustomDropDown from "src/flows/components/CustomDropDown";
import {
  CredentialDetailEndpoint,
  useProprietaryCredentials,
} from "src/stores/useProprietaryCredentials";
import { useCredentials } from "src/stores/useCredentials";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { decryptString } from "src/utils/encryptionUtils";
import CustomPopover from "src/flows/components/customPopover";
import { useOverlay } from "src/context/overlayContext";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { successToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";

function SortIcon({ sortOrder }: { sortOrder: string }) {
  return sortOrder ? (
    sortOrder === "descend" ? (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z"
          fill="#B3B3B3"
        />
      </svg>
    ) : (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z"
          fill="#B3B3B3"
        />
      </svg>
    )
  ) : null;
}

export default function ViewProjectCredential() {
  const [showKey, setShowKey] = useState(false);
  const { openDrawerWithStep, openDrawer } = useDrawer();
  const [showConfirm, setShowConfirm] = useState(false);
  const {
    deleteProjectCredentials,
    credentialDetails,
    selectedCredential,
    refresh,
  } = useCredentials();
  const [decryptedKey, setDecryptedKey] = useState("");
  const [copyText, setCopiedText] = useState<string>("Copy");
  const { setOverlayVisible } = useOverlay();
  const { closeDrawer } = useDrawer();

  const decryptKey = async (key) => {
    try {
      const result = await decryptString(key);
      return result;
    } catch (error) {
      console.error("Error:", error);
    }
  };

  useEffect(() => {
    const fetchDecryptedKey = async () => {
      if (selectedCredential?.key) {
        console.log("selectedCredential.key", selectedCredential.key);
        const key = await decryptKey(selectedCredential.key);
        console.log("key", key);
        setDecryptedKey(key);
      }
    };

    fetchDecryptedKey();
  }, [selectedCredential]);
  const handleCopy = async (text: string) => {
    await copyToClipboard(text, {
      onSuccess: () => setCopiedText("Copied"),
      onError: () => setCopiedText("Failed to copy"),
    });
  };

  useEffect(() => {
    setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);
  }, [copyText]);

  const firstLineText = `Are you sure you want to delete this credential?`;
  const secondLineText = `You are about to delete ${selectedCredential?.["name"]}`;

  return (
    <BudForm data={{}}>
      <BudWraperBox>
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warining"
              title={firstLineText}
              description={secondLineText}
              confirmText="Delete Credential"
              cancelText="Cancel"
              confirmAction={async () => {
                const result = await deleteProjectCredentials(
                  selectedCredential?.id,
                );
                if (result) {
                  successToast("Credential deleted successfully");
                  await refresh();
                  closeDrawer();
                }
                setShowConfirm(false);
              }}
              cancelAction={() => {
                setShowConfirm(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <BudDrawerLayout>
          <div
            className={`px-[1.4rem] pb-[.9rem] rounded-ss-lg rounded-se-lg pt-[1.1rem] border-b-[.5px] border-b-[#1F1F1F] relative`}
          >
            <div className="flex justify-between align-center">
              <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0">
                {selectedCredential?.["name"]}
              </Text_14_400_EEEEEE>
            </div>
            <Text_12_400_757575 className="pt-[.55rem] leading-[1.05rem]">
              Following is the list of Keys
            </Text_12_400_757575>
            <div className="absolute right-[.5rem] top-[.5rem]">
              <CustomDropDown
                buttonContent={
                  <div className="px-[.3rem] my-[0] py-[0.02rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/threeDots.png"
                      alt="info"
                      style={{ width: "0.1125rem", height: ".6rem" }}
                    />
                  </div>
                }
                items={[
                  {
                    key: "1",
                    label: <Text_12_400_EEEEEE>Edit</Text_12_400_EEEEEE>,
                    onClick: () => openDrawer("edit-project-credential"),
                  },
                  {
                    key: "2",
                    label: <Text_12_400_EEEEEE>Delete</Text_12_400_EEEEEE>,
                    onClick: () => {
                      setShowConfirm(true);
                    },
                  },
                ]}
              />
            </div>
          </div>
          <div className=" px-[1.4rem] pt-[1.4rem] border-b-[1px] border-b-[#1F1F1F]">
            <div className="flex justify-between pt-[1rem] flex-wrap items-center pb-[1.2rem] gap-[1.2rem]">
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className=" flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/key.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3>Key</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  {showKey ? (
                    <Text_12_400_EEEEEE className="leading-[100%]  !leading-[0.875rem] max-w-[90%] truncate">
                      {decryptedKey || "Loading..."}
                    </Text_12_400_EEEEEE>
                  ) : (
                    <Text_10_400_EEEEEE className="leading-[0.875rem] max-w-[90%] truncate">
                      {decryptedKey?.replace(/./g, "⏺")}
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
                    <CustomPopover
                      title={copyText}
                      contentClassNames="py-[.3rem]"
                    >
                      <div
                        className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center ml-[.4rem] cursor-pointer hover:bg-[#1F1F1F]"
                        onClick={() => handleCopy(decryptedKey)}
                      >
                        <Image
                          preview={false}
                          src="/images/drawer/Copy.png"
                          alt="info"
                          style={{ height: ".75rem" }}
                        />
                      </div>
                    </CustomPopover>
                  </div>
                </div>
              </div>
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className=" flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/note.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3 className="">
                    Project name
                  </Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem] w-[280px] truncate">
                    {selectedCredential?.project?.name}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className=" flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/calander.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3 className="">
                    Expiry Date
                  </Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto">
                  <Text_12_400_EEEEEE className="leading-[.875rem]  w-[280px] truncate">
                    {selectedCredential?.expiry
                      ? formatDate(selectedCredential?.expiry)
                      : "--"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className=" flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/calander.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3 className="">
                    Last Used
                  </Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem]  w-[280px] truncate">
                    {selectedCredential?.last_used_at
                      ? formatDate(selectedCredential?.last_used_at)
                      : "--"}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
              <div className="flex justify-between items-center w-full gap-[.8rem]">
                <div className=" flex justify-start items-center gap-[.4rem] min-w-[25%]">
                  <div className="w-[.75rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/dollar.png"
                      alt="info"
                      style={{ width: ".75rem" }}
                    />
                  </div>
                  <Text_12_400_B3B3B3 className="">
                    Max Budget
                  </Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-between w-full flex-auto max-w-[73%]">
                  <Text_12_400_EEEEEE className="leading-[.875rem]  w-[280px] truncate">
                    {selectedCredential?.max_budget
                      ? "$" + selectedCredential?.max_budget
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
