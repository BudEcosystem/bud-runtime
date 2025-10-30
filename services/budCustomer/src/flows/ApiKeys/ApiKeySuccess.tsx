import React, { useEffect, useState } from "react";
import { Image, Button } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import {
  Text_12_300_EEEEEE,
  Text_13_400_EEEEEE,
  Text_24_600_EEEEEE,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Icon } from "@iconify/react/dist/iconify.js";
import { successToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";

const ApiKeySuccess = () => {
  const { closeDrawer } = useDrawer();
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Get the API key from localStorage (temporarily stored)
    const key = localStorage.getItem("temp_api_key");
    if (key) {
      setApiKey(key);
      // Clean up after retrieving
      localStorage.removeItem("temp_api_key");
    }
  }, []);

  const handleCopyKey = async () => {
    if (apiKey) {
      await copyToClipboard(apiKey, {
        onSuccess: () => {
          setCopied(true);
          successToast("API key copied to clipboard!");
          setTimeout(() => setCopied(false), 2000);
        },
        onError: () => {
          setCopied(false);
          successToast("Failed to copy API key");
        },
      });
    }
  };

  return (
    <BudForm
      data={{}}
      nextText="Ok"
      onNext={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center p-[2.5rem]">
            <div className="align-center mb-4">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="success"
                width={140}
                height={129}
              />
            </div>

            <div className="max-w-[84%] mt-[1rem] mb-[2rem] flex flex-col items-center justify-center">
              <Text_24_600_EEEEEE className="text-[black] dark:text-[#EEEEEE] text-center leading-[2rem] mb-[1.2rem]">
                API Key Created Successfully!
              </Text_24_600_EEEEEE>
            </div>

            {apiKey && (
              <>
                <div className="bg-[#DE9C5C1A] border border-[#DE9C5C33] rounded-[8px] p-[1rem] mb-[1.5rem] flex gap-[0.75rem] w-full max-w-[500px]">
                  <Icon
                    icon="ph:warning"
                    className="text-[#DE9C5C] text-[1.25rem] flex-shrink-0"
                  />
                  <Text_13_400_EEEEEE className="text-[#DE9C5C] dark:text-[#DE9C5C]">
                    Save this key now. You won&apos;t be able to see it again!
                  </Text_13_400_EEEEEE>
                </div>

                <div className="bg-gray-100 dark:bg-[#1F1F1F] border border-gray-300 dark:border-[#2F2F2F] rounded-[8px] p-[1rem] flex items-center justify-between w-full max-w-[500px]">
                  <code className="text-gray-900 dark:text-[#EEEEEE] text-[0.875rem] break-all flex-1">
                    {apiKey}
                  </code>
                  <Button
                    type="text"
                    icon={
                      <Icon
                        icon={copied ? "ph:check" : "ph:copy"}
                        className="text-[1.25rem]"
                      />
                    }
                    onClick={handleCopyKey}
                    className="text-gray-600 dark:text-[#757575] hover:text-gray-900 dark:hover:text-[#EEEEEE] ml-[1rem]"
                  />
                </div>
              </>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default ApiKeySuccess;
