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
import { useOverlay } from "src/context/overlayContext";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { successToast } from "@/components/toast";
import { decryptString } from "src/utils/encryptionUtils";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import CustomPopover from "src/flows/components/customPopover";

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

export default function ViewCredential() {
  const [showKey, setShowKey] = useState(false);
  const { openDrawerWithStep } = useDrawer();
  const [showConfirm, setShowConfirm] = useState(false);
  const { credentialDetails, deleteProprietaryCredential, refresh } =
    useProprietaryCredentials();
  const { setOverlayVisible } = useOverlay();
  const { closeDrawer } = useDrawer();
  const [decryptData, setDecryptData] = useState<any>(null);
  const [copyText, setCopiedText] = useState<string>("Copy");

  useEffect(() => {
    setTimeout(() => {
      setCopiedText("Copy");
    }, 3000);
  }, [copyText]);

  const handleCopy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        // message.success('Text copied to clipboard!');
        setCopiedText("Copied..");
      })
      .catch(() => {
        // message.error('Failed to copy text.');
        setCopiedText("Failed to copy");
      });
  };

  useEffect(() => {
    const decryptData = async () => {
      const result: any = {};
      for (const key of Object.keys(credentialDetails.other_provider_creds)) {
        result[key] = await decryptString(
          credentialDetails.other_provider_creds[key],
        );
      }
      setDecryptData(result);
    };
    if (credentialDetails?.other_provider_creds) decryptData();
  }, [credentialDetails]);

  const firstLineText = `Are you sure you want to delete this proprietary credential?`;
  const secondLineText = `You are about to delete ${credentialDetails?.["name"]}`;

  return (
    <BudForm data={{}}>
      <BudWraperBox classNames="mt-[1.9375rem]">
        {showConfirm && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title={firstLineText}
              description={secondLineText}
              confirmText="Delete Credential"
              cancelText="Cancel"
              confirmAction={async () => {
                const result = await deleteProprietaryCredential(
                  credentialDetails.id,
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
          <div className=" px-[1.4rem] pt-[1.4rem] border-b-[1px] border-b-[#1F1F1F]">
            <div className="w-full flex justify-between items-start">
              <Text_14_400_EEEEEE>
                {credentialDetails?.["name"]}
              </Text_14_400_EEEEEE>
              <div>
                <CustomDropDown
                  parentClassNames="oneDrop"
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
                    // {
                    //   key: '1',
                    //   label: (
                    //     <Text_12_400_EEEEEE>Edit</Text_12_400_EEEEEE>
                    //   ),
                    //   onClick: () => openDrawerWithStep('edit-model')
                    // },
                    {
                      key: "1",
                      label: <Text_12_400_EEEEEE>Delete</Text_12_400_EEEEEE>,
                      onClick: () => {
                        setShowConfirm(true);
                      },
                    },
                  ]}
                />
              </div>
            </div>
            <div className="flex justify-between pt-[.7rem] flex-wrap items-center pb-[1rem] gap-[.9rem]">
              {decryptData && (
                <>
                  {Object.keys(decryptData).map((key, index) => (
                    <div
                      className="flex justify-between items-center w-full gap-[.5rem]"
                      key={index}
                    >
                      <div className="width-120">
                        <Text_12_400_B3B3B3>{key}</Text_12_400_B3B3B3>
                      </div>
                      <div className="flex items-center justify-start w-full gap-x-[.5rem]">
                        {showKey ? (
                          <Text_12_400_EEEEEE className="leading-[100%]  !leading-[0.875rem] max-w-[300px] truncate">
                            {decryptData[key] || "Loading..."}
                          </Text_12_400_EEEEEE>
                        ) : (
                          <Text_10_400_EEEEEE className="leading-[0.875rem] max-w-[300px] truncate">
                            {decryptData[key]?.replace(/./g, "⏺")}
                          </Text_10_400_EEEEEE>
                        )}
                        <div className="flex justiify-end items-center gap-[.3rem]">
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
                          {decryptData[key] && (
                            <CustomPopover
                              title={copyText}
                              contentClassNames=""
                            >
                              <div
                                className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center cursor-pointer hover:bg-[#1F1F1F]"
                                onClick={() => handleCopy(decryptData[key])}
                              >
                                <Image
                                  preview={false}
                                  src="/images/drawer/Copy.png"
                                  alt="info"
                                  style={{ height: ".825rem" }}
                                />
                              </div>
                            </CustomPopover>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
          <div className="pb-[1.8rem] pt-[.4rem] px-[1.4rem]">
            <Table<CredentialDetailEndpoint>
              columns={[
                {
                  title: "Deployment Name",
                  dataIndex: "name",
                  key: "name",
                  width: 150,
                  render: (text) => (
                    <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
                  ),
                },
                {
                  title: "Status",
                  dataIndex: "status",
                  key: "status",
                  width: 150,
                  render: (text) => (
                    <div className="flex">
                      <ProjectTags
                        name={capitalize(text)}
                        color={endpointStatusMapping[capitalize(text)]}
                      />
                    </div>
                  ),
                },
                {
                  title: "Project Name",
                  dataIndex: "project_info",
                  key: "project_info",
                  width: 150,
                  render: (text) => (
                    <Text_12_400_EEEEEE>{text.name}</Text_12_400_EEEEEE>
                  ),
                  sorter: (a, b) =>
                    a.project_info?.name.localeCompare(b.project_info?.name),
                  sortIcon: SortIcon,
                },
                {
                  title: "Model Name",
                  dataIndex: "model_info",
                  key: "model_info",
                  render: (text) => (
                    <div className="select-none flex items-center">
                      <div className="w-[0.875rem] h-[0.875rem]">
                        <Image
                          src={`${assetBaseUrl}${text?.icon}`}
                          preview={false}
                          style={{ width: "0.875rem" }}
                        />
                      </div>
                      <Text_12_300_EEEEEE
                        className="flex-auto truncate max-w-[90%]"
                        style={{ marginLeft: 10 }}
                      >
                        {text.name}
                      </Text_12_300_EEEEEE>
                    </div>
                  ),
                  sorter: (a, b) =>
                    a.model_info?.name.localeCompare(b.model_info?.name),
                  sortIcon: SortIcon,
                },
                {
                  title: "Type",
                  dataIndex: "model_info",
                  key: "model_info",
                  render: (text) => (
                    <Text_12_400_EEEEEE>{text.modality}</Text_12_400_EEEEEE>
                  ),
                  sorter: (a, b) =>
                    a.model_info?.modality.localeCompare(
                      b.model_info?.modality,
                    ),
                  sortIcon: SortIcon,
                },
                {
                  title: "Created On",
                  dataIndex: "created_at",
                  key: "created_at",
                  render: (text) => (
                    <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>
                  ),
                  sorter: (a, b) =>
                    new Date(a.created_at).getTime() -
                    new Date(b.created_at).getTime(),
                  sortIcon: SortIcon,
                },
              ]}
              pagination={false}
              dataSource={credentialDetails?.endpoints}
              bordered={false}
              footer={null}
              virtual
              onRow={() => {
                return {
                  onClick: async () => {
                    // openDrawer("view-credentials")
                  },
                };
              }}
              showSorterTooltip={false}
              title={() => (
                <div className="flex flex-col justify-start items-start  py-[1rem] gap-[.25rem]">
                  <Text_14_400_EEEEEE>Deployments</Text_14_400_EEEEEE>
                  <Text_12_400_757575>
                    Following is the list of deployments
                  </Text_12_400_757575>
                </div>
              )}
              className="borderlessTable"
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
