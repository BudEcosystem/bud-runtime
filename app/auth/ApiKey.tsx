import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Form, Image, Input } from "antd";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/lib/text";
import { PrimaryButton } from "../components/uiComponents/inputs";
import { EyeClosedIcon, EyeIcon } from "lucide-react";

function ApiKey() {
  const [apiKey, setApiKey] = useState<string>("");
  const router = useRouter();
  const [isShow, setIsShow] = useState(false);
  const [form] = Form.useForm();
  const handleAdd = () => {
    router.replace(`?api_key=${apiKey}`);
  };

  return (
    <>
      <div className="mb-8">
        <div className="flex justify-center items-center mb-[1.12rem]">
          <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center">
            Hey, hello 👇
          </Text_32_500_FFFFFF>
          {/* <video
                  src="/webm/wave.webm"
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-[45px] h-auto mb-1 2xl:w-12"
                /> */}
        </div>
        <Text_12_400_B3B3B3 className="text-center">
          Please enter API key
        </Text_12_400_B3B3B3>
      </div>

      <Form
        feedbackIcons={({ status, errors, warnings }) => {
          // return <FeedbackIcons status={status} errors={errors} warnings={warnings} />
          return {
            error: (
              <Image
                src="/icons/warning.svg"
                alt="error"
                width={"1rem"}
                height={"1rem"}
              />
            ),
            success: <div />,
            warning: <div />,
            "": <div />,
          };
        }}
        className="mt-[1.6em]"
        form={form}
      >
        <Form.Item
          hasFeedback
          name="password"
          className="mb-[2rem]"
          rules={[
            {
              required: true,
              message: "Please input your password!",
            },
            {
              min: 8,
              message: "Password must be at least 8 characters long",
            },
          ]}
        >
          <div
            className={`flex items-center border rounded-[6px] relative !bg-[transparent]`}
          >
            <div className="">
              <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem] z-10">
                API Key
              </Text_12_300_EEEEEE>
            </div>
            <Input
              placeholder="Enter key"
              className={`passwordField h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE]  placeholder:text-[#808080] font-light outline-none !bg-[transparent] border rounded-[6px] pt-[.8rem] pb-[.53rem]`}
              type={isShow ? "text" : "password"}
              classNames={{
                input: "rounded-l-[5px] border-none!",
              }}
              autoComplete="no-fill"
              variant="borderless"
              suffix={
                isShow ? (
                  <EyeIcon
                    onClick={() => setIsShow(!isShow)}
                    className="text-[#808080] cursor-pointer"
                  />
                ) : (
                  <EyeClosedIcon
                    onClick={() => setIsShow(!isShow)}
                    className="text-[#808080] cursor-pointer"
                  />
                )
              }
              title="API Key"
              name="apiKey"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </Form.Item>
        <PrimaryButton
          type="click"
          classNames="w-[100%] mt-[1.6rem]"
          onClick={handleAdd}
        >
          Add
        </PrimaryButton>
      </Form>
      <div className="flex justify-center items-center mt-[2rem] cursor-pointer group">
        <Text_12_400_EEEEEE className="transition-transform duration-300 ease-out group-hover:-translate-x-1">
          Skip
        </Text_12_400_EEEEEE>
        <div className="w-[1.375rem] h-[1.375rem] flex justify-center items-center bg-[#18191B] rounded-full ml-[.5rem] transition-transform duration-300 ease-out group-hover:translate-x-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="6"
            height="10"
            viewBox="0 0 6 10"
            fill="none"
          >
            <path
              d="M0.888572 0.922852L4.85742 4.8917L0.888572 8.86055"
              stroke="white"
              strokeWidth="1.35823"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>
    </>
  );
}

export default ApiKey;
