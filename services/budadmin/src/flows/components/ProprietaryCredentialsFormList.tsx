import React, { useEffect, useState } from "react";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { Input, Image, Checkbox, Form } from "antd"; // Added Checkbox import
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import { useModels } from "src/hooks/useModels";
import {
  Credentials,
  useProprietaryCredentials,
} from "src/stores/useProprietaryCredentials";
import { useDeployModel } from "src/stores/useDeployModel";
import { decryptString } from "src/utils/encryptionUtils";
import CustomPopover from "./customPopover";

function CredentialsItem({
  data,
  selected,
  onSelect,
}: {
  data: Credentials;
  selected: boolean;
  onSelect?: (selected: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [copyText, setCopiedText] = useState<string>("Copy");

  const toggleShowKey = (key: string) => {
    setShowKeys((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  useEffect(() => {
    const decryptData = async () => {
      for (const key of Object.keys(data.other_provider_creds)) {
        data.other_provider_creds[key] = await decryptString(
          data.other_provider_creds[key],
        );
      }
    };
    if (data?.other_provider_creds) decryptData();
  }, [data]);

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

  return (
    <div
      className={`px-[1.4rem] border-b-[1px] border-b-[#FFFFFF08] border-t-[1px] border-t-[transparent] hover:border-t-[#757575] hover:border-b-[#757575]
        ${
          open
            ? "!border-b-[#757575] !border-t-[#757575]"
            : "border-b-[#FFFFFF08] border-t-[transparent] hover:border-t-[#757575] hover:border-b-[#757575]" // Styles when open is false
        }
      `}
    >
      <div className="flex justify-between items-center py-[1.2rem]">
        <Text_14_400_EEEEEE>{data.name}</Text_14_400_EEEEEE>
        <div className="flex justify-end items-start">
          <div
            className="w-[0.9375rem] h-[0.9375rem] mr-[0.6rem] cursor-pointer"
            onClick={() => setOpen(!open)}
          >
            <Image
              preview={false}
              width={15}
              src="/images/drawer/ChevronUp.png"
              alt="Logo"
              style={{
                transform: !open ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.3s ease",
              }}
            />
          </div>
          <div>
            <Checkbox
              onChange={(newValue) => {
                onSelect(newValue.target.checked);
              }}
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        </div>
      </div>
      {open && (
        <div className="flex justify-between flex-wrap items-center mt-[-.4rem] pb-[1.2rem] gap-[1.2rem]">
          {Object.keys(data.other_provider_creds).map((key, index) => (
            <div
              className="flex justify-between items-center w-full gap-[.8rem]"
              key={index}
            >
              <div className="min-w-[33%]">
                <Text_12_400_B3B3B3>{key}</Text_12_400_B3B3B3>
              </div>
              <div className="flex items-center justify-between w-full max-w-[64%]">
                {showKeys[key] ? (
                  <Text_12_400_EEEEEE className="leading-[100%] max-w-[94%] truncate">
                    {/* {data.other_provider_creds[key]?.substring(0, 36)}
                    {data.other_provider_creds[key]?.length > 50 ? "..." : ""} */}
                    {data.other_provider_creds[key]}
                  </Text_12_400_EEEEEE>
                ) : (
                  <Text_12_400_EEEEEE className="leading-[100%]">
                    ********
                  </Text_12_400_EEEEEE>
                )}
                <div className="flex items-center justify-end gap-[.3rem]">
                  <button
                    onClick={() => toggleShowKey(key)}
                    className="ml-[.5rem]"
                  >
                    {showKeys[key] ? (
                      <EyeOutlined className="text-[#B3B3B3]" />
                    ) : (
                      <EyeInvisibleOutlined className="text-[#B3B3B3]" />
                    )}
                  </button>
                  <CustomPopover title={copyText} contentClassNames="">
                    <div
                      className="w-[1.25rem] h-[1.25rem] rounded-[4px] flex justify-center items-center cursor-pointer hover:bg-[#1F1F1F]"
                      onClick={() => handleCopy(data.other_provider_creds[key])}
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
          ))}
        </div>
      )}
    </div>
  );
}

function CredentialsList() {
  const { selectedModel, selectedCredentials, setSelectedCredentials } =
    useDeployModel();
  const { credentials } = useProprietaryCredentials();

  const handleSelect = (data: Credentials) => {
    setSelectedCredentials(data);
  };

  return (
    <div>
      {credentials?.map((item, index) => (
        <CredentialsItem
          key={index}
          data={item}
          onSelect={(selected) => {
            handleSelect(selected ? item : null);
          }}
          selected={selectedCredentials?.id === item.id}
        />
      ))}
    </div>
  );
}

function ProprietaryCredentialsFormList({
  providerType,
  provider,
}: {
  providerType: string;
  provider?: any;
}) {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const [enterCredentials, setEnterCredentials] = useState(false);
  const { selectedModel } = useModels();
  const { currentWorkflow, selectedModel: currentSelectedModel } =
    useDeployModel();
  const {
    getProviderInfo,
    providerInfo,
    createProprietaryCredentials,
    getCredentials,
    credentials,
    setSelectedProvider,
  } = useProprietaryCredentials();
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    console.log("provider", provider);
    console.log("currentSelectedModel", currentSelectedModel);
    setSelectedProvider(currentSelectedModel?.provider || provider?.id);
  }, [currentSelectedModel, provider]);

  useEffect(() => {
    if (providerType) getProviderInfo(providerType);
  }, [providerType]);

  useEffect(() => {
    if (providerType)
      getCredentials({
        type: providerType,
      });
  }, [providerType]);

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const payload = Object.assign({}, values);
      delete payload.name;
      Object.keys(payload).forEach((key) => {
        if (!payload[key]) {
          delete payload[key];
        }
      });
      const result = await createProprietaryCredentials(
        values.name,
        providerType,
        payload,
      );
      if (result) {
        await getCredentials({
          type: providerType,
        });
        openEnterCredentials(false);
      }
    } catch (error) {
    } finally {
      setLoading(false);
    }
  };

  const openEnterCredentials = (value) => {
    setEnterCredentials(value);
    form.resetFields();
  };

  return (
    <BudDrawerLayout>
      <DrawerTitleCard
        title="Select or Add Credentials"
        description="Add Credentials now to have a smoother deployment process"
      />
      <div className="mt-[1.7rem]">
        <div className="px-[1.4rem] flex justify-between items-center pb-[1.7rem] border-b-[.5px] border-b-[#1F1F1F]">
          <div className="flex justify-start items-center">
            <Text_12_400_757575>Credentials Available&nbsp;</Text_12_400_757575>
            <Text_12_600_EEEEEE>
              {credentials?.length || "0"}
            </Text_12_600_EEEEEE>
          </div>
          <PrimaryButton
            type="submit"
            onClick={() => openEnterCredentials(true)}
            classNames="px-[.9rem]"
          >
            + Add Credentials
          </PrimaryButton>
        </div>
        <div>
          {enterCredentials && providerInfo && (
            <Form
              className="border-t-[1px] border-b-[1px] border-t-[#757575] border-b-[#757575] bg-[#FFFFFF08] box-border"
              form={form}
              layout="vertical"
              validateTrigger="onBlur"
              onFinish={handleSubmit}
              initialValues={{
                name: "",
                ...providerInfo?.reduce((acc, item) => {
                  acc[item.field] = "";
                  return acc;
                }),
              }}
            >
              <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                <Text_14_400_EEEEEE className="pt-[.55rem]">
                  Enter Credential Details
                </Text_14_400_EEEEEE>
                <div
                  className="w-[.75rem] h-[.75rem] cursor-pointer"
                  onClick={() => openEnterCredentials(false)}
                >
                  <Image
                    preview={false}
                    src="/images/drawer/close.png"
                    alt="info"
                    style={{ width: ".75rem" }}
                  />
                </div>
              </div>
              <div className="px-[1.4rem] flex justify-between items-center flex-wrap gap-[2rem]">
                <Form.Item
                  hasFeedback
                  name="name"
                  rules={[
                    {
                      required: true,
                      message: "Please input your API key name",
                    },
                  ]}
                  className="flex justify-between items-center flex-row w-full"
                >
                  <div className="w-full flex justify-between items-center gap-[.8rem]">
                    <div className="min-w-[33%]">
                      <Text_12_400_B3B3B3 className="text-nowrap">
                        API key name
                      </Text_12_400_B3B3B3>
                    </div>
                    <Input
                      name="name"
                      className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full"
                      placeholder="Enter API key name"
                      onChange={(e) =>
                        form.setFieldsValue({ name: e.target.value })
                      }
                    />
                  </div>
                </Form.Item>
                {providerInfo?.map((item, index) => (
                  <Form.Item
                    hasFeedback
                    key={index}
                    name={item.field}
                    rules={[
                      {
                        required: item.required,
                        message: `Please input your ${item.label}`,
                      },
                      item?.type === "email" && {
                        required: item.required,
                        type: "email",
                        message: "Please input a valid email",
                      },
                      item?.type === "url" && {
                        required: item.required,
                        type: "url",
                        message: "Please input a valid URL",
                      },
                    ]}
                    className="flex justify-between items-center w-full flex-row"
                  >
                    <div className="w-full flex justify-between items-center gap-[.8rem] relative">
                      <div className="min-w-[33%]">
                        <Text_12_400_B3B3B3 className="text-nowrap">
                          {item.label}
                        </Text_12_400_B3B3B3>
                      </div>
                      <Input
                        name={item.field}
                        className="border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full max-w-[64%] pr-[1.5rem]"
                        placeholder={item.description}
                        type={
                          item.type === "password" && showKey
                            ? "text"
                            : item.type
                        }
                        required={item.required}
                        onChange={(e) =>
                          form.setFieldsValue({ [item.field]: e.target.value })
                        }
                      />
                      {item.type === "password" && (
                        <div
                          onClick={() => setShowKey(!showKey)}
                          className="ml-[.5rem] absolute right-[.4rem] z-10 cursor-pointer"
                        >
                          {showKey ? (
                            <EyeOutlined className="text-[#B3B3B3]" />
                          ) : (
                            <EyeInvisibleOutlined className="text-[#B3B3B3]" />
                          )}
                        </div>
                      )}
                    </div>
                  </Form.Item>
                ))}
              </div>
              <div className="px-[1.4rem] flex justify-end pt-[1.7rem] pb-[1.1rem]">
                <PrimaryButton
                  type="submit"
                  disabled={
                    form.getFieldsError().filter(({ errors }) => errors.length)
                      .length > 0
                  }
                  classNames="!px-[.1rem]"
                  onClick={() => form.submit()}
                >
                  + Add
                </PrimaryButton>
              </div>
            </Form>
          )}
          <CredentialsList />
        </div>
      </div>
    </BudDrawerLayout>
  );
}

export default ProprietaryCredentialsFormList;
