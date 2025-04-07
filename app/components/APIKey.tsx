import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Form, Image, Input } from "antd";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_300_EEEEEE,
  Text_18_500_EEEEEE,
  Text_26_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/lib/text";
import { PrimaryButton } from "./uiComponents/inputs";
import { EyeClosedIcon, EyeIcon } from "lucide-react";
import { useLoader } from "../context/appContext";
import { useEndPoints } from "./bud/hooks/useEndPoint";

function APIKey({
  onLoginSuccess,
}: {
  onLoginSuccess: (apiKey: string) => void;
}) {
  const { showLoader, hideLoader, isLoading } = useLoader();
  const { getEndPoints } = useEndPoints();
  const router = useRouter();
  const [isShow, setIsShow] = useState(false);
  const [form] = Form.useForm();
  const [isInvalidApiKey, setIsInvalidApiKey] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const handleAdd = async () => {
    form.submit();
    if (!apiKey) {
      return;
    }
    showLoader();
    const endpointResult = await getEndPoints({ page: 1, limit: 25, apiKey });
    if(!Array.isArray(endpointResult)){
      setIsInvalidApiKey(true);
    } else {
      onLoginSuccess(apiKey);
      router.replace(`?api_key=${apiKey}`);
    }
    setTimeout(() => {
      hideLoader();
    }, 2000);
  }

  useEffect(() => {
    const apiKey = new URLSearchParams(window.location.search).get("api_key");
    if (apiKey) {
      setApiKey(apiKey);
    }
    setTimeout(() => {
      hideLoader();
    }, 2000);
  }, []);

  if (isLoading) {
    return null;
  }

  return (
    <div className="w-full h-screen logginBg box-border relative">
      <div className="loginWrap w-full h-full loginBg-glass flex justify-between box-border ">
        <div className="loginLeft relative login-left-bg overflow-hidden rounded-[15px] w-[56.4%] m-[.8rem] p-[.8rem] overflow-hidden">
          {/* <Image
            preview={false}
            alt=""
            src="/images/purple-shadow.png"
            className="absolute bottom-[-28em] left-[-29em] rotate-[14deg] opacity-[.3]"
          /> */}
          <div className="flex flex-col justify-between w-[100%] 2xl:max-w-[500px] 1680px:max-w-[650px] h-full px-[3.5rem] pt-[3rem] pb-[2.9rem]">
            <Image
              alt=""
              src="/images/BudLogo.png"
              preview={false}
              style={{ width: "8em" }}
              className="w-[6.6em] h-auto"
            />
            <div className="logo-text text-[2.25em] 2xl:text-[2.5rem] 1680px:text-[2.4rem] text-white open-sans tracking-[.0rem] leading-[3.1rem] w-[700px] 1680px:w-[700px] 2560px:w-[900px]">
            Bud Studio. <br /> Any Model in Any Cloud, with Any hardware.<br />  One Platform.
            </div>
          </div>
        </div>
        <div className="loginRight  w-[43.6%] h-full flex justify-center items-center">
          <div className="w-[51.5%]">
            <div className="mb-[4rem]">
              <div className="flex justify-center items-center mb-[1.12rem]">
                <div className="text-[#FFFFFF] text-[2.5rem] font-bold leading-[24px] tracking-[.01em] leading-[100%] text-center">
                  Hey, hello 👇
                </div>
                {/* <video
                  src="/webm/wave.webm"
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-[45px] h-auto mb-1 2xl:w-12"
                /> */}
              </div>
              <Text_14_300_EEEEEE className="text-center">
                Please enter the Bud API key to access the playground
              </Text_14_300_EEEEEE>
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
                    className={`passwordField h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE]  placeholder:text-[#808080] font-light outline-none !bg-[transparent] border rounded-[6px] pt-[.6rem] pb-[.6rem]`}
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
                    onPressEnter={handleAdd}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
              </Form.Item>
              <PrimaryButton
                type="click"
                classNames="w-[100%] mt-[1.6rem]"
                onClick={handleAdd}
              >
                Login
              </PrimaryButton>
            </Form>
            {isInvalidApiKey && <div className="text-center text-[#ec7575] text-[0.75rem] bg-[#ec75751a] border border-[#ec7575] rounded-[6px] p-[.5rem] mt-[3rem]">
              Invalid API Key
            </div>}
            {/* <div className="flex justify-center items-center mt-[2rem] cursor-pointer group">
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
            </div> */}
          </div>
        </div>
      </div>
    </div>
    // <div className="w-full max-w-[20rem]">
    //   <LabelInput
    //     title="API Key"
    //     value={apiKey}
    //     onChange={(value) => setApiKey(value)}
    //     description="Your API key is used to authenticate your requests to the API."
    //     placeholder="Enter your API key"
    //     className="w-full"
    //   />
    //   <div className="w-full flex justify-center items-center">
    //     <button
    //       className="w-[8rem] bg-[#1E0C34] text-[#FFF] rounded-[6px] py-[.75rem] px-[1rem] font-[400] text-[.75rem] mt-[1rem] border-[#965CDE] border-[1px] hover:bg-[#965CDE] hover:text-[#101010] active:bg-[#965CDE] active:text-[#101010] cursor-pointer"
    //       onClick={handleAdd}
    //     >
    //       Add
    //     </button>
    //   </div>
    // </div>
  );
}

export default APIKey;
