"use client";

import React, { useEffect, useState } from "react";
import { Form, Image, Input } from "antd";
import { useAuth } from "../context/AuthContext";
import { Text_12_300_EEEEEE, Text_14_300_EEEEEE } from "@/lib/text";
import { EyeClosedIcon, EyeIcon } from "lucide-react";
import { PrimaryButton } from "../components/uiComponents/inputs";
import { useRouter } from "next/navigation";
import { useLoader } from "../context/LoaderContext";
import GameOfLifeBackground from "../components/bud/components/GameOfLifeBg";

export default function Login() {
    const { apiKey, login, isLoading: authLoading, isSessionValid } = useAuth();
    const { showLoader, hideLoader, isLoading } = useLoader();
    const router = useRouter();
    const [form] = Form.useForm();
    const [isShow, setIsShow] = useState(false);
    const [isInvalidApiKey, setIsInvalidApiKey] = useState(false);
    const [key, setKey] = useState("");

    // Build chat redirect URL preserving relevant parameters
    const getChatRedirectUrl = () => {
        if (typeof window === 'undefined') return '/chat';
        const params = new URLSearchParams(window.location.search);
        // Parameters to exclude (auth-related)
        const excludeParams = ['refresh_token', 'access_key', 'embedded'];
        const preservedParams = new URLSearchParams();

        params.forEach((value, key) => {
            if (!excludeParams.includes(key)) {
                preservedParams.append(key, value);
            }
        });

        const queryString = preservedParams.toString();
        return queryString ? `/chat?${queryString}` : '/chat';
    };

    const handleAdd = async (refreshToken?: string) => {
        if(!refreshToken) {
          form.submit();
        }
        const keyToValidate = refreshToken || key;
        if(!keyToValidate) return;
        showLoader();
        const isLoginSuccessful = await login(key, refreshToken);
        if(isLoginSuccessful) {
            router.replace(getChatRedirectUrl());
        } else {
            setIsInvalidApiKey(true);
        }
        hideLoader();
    }

    // Handle authentication state changes
    useEffect(() => {
        if (authLoading) {
            return; // Wait for auth to finish loading
        }

        if (apiKey || isSessionValid) {
            // Already authenticated, redirect to chat
            router.replace(getChatRedirectUrl());
        } else {
            // Not authenticated, show login form
            hideLoader();
        }
    }, [apiKey, isSessionValid, authLoading, router, hideLoader]);
    return (
      <div className={`w-full h-screen logginBg box-border relative overflow-hidden ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
        <div className="loginWrap w-full h-full loginBg-glass flex justify-between box-border ">
          <div className="loginLeft relative login-left-bg overflow-hidden rounded-[15px] w-[56.4%] m-[.8rem] p-[.8rem] overflow-hidden">
            <div className="flex flex-col justify-between w-[100%] max-w-[800px] 1680px:max-w-[900px] 2560px:max-w-[900px] h-full px-[3.5rem] pt-[3rem] pb-[2.9rem]">
              <GameOfLifeBackground />
            <Image
              alt=""
              src="/images/logo-white.png"
              preview={false}
              style={{ width: "8em" }}
              className="w-[6.6em] h-auto relative z-10"
            />

            <div className="relative z-10 logo-text line-clamp-2 text-[2.25em] 2xl:text-[2.5rem] 1680px:text-[2.4rem] text-white open-sans tracking-[.0rem] leading-[4rem]">
            <strong>Bud Studio.</strong> <br /> Any Model in Any Cloud, with Any hardware.
            </div>
          </div>
        </div>
        <div className="loginRight  w-[43.6%] h-full flex justify-center items-center">
          <div className="w-[60%]">
            <div className="mb-[4rem]">
              <div className="flex justify-center items-center mb-[1.12rem]">
                <div className="flex justify-center items-center text-[#FFFFFF] text-[2.5rem] font-bold leading-[24px] tracking-[.01em] leading-[100%] text-center">
                  <span>Hello there!</span>
                  <Image src="/images/hand-waving-hand.gif" preview={false} alt="bud-logo" width={35} height={35} className="ml-[1rem]" />
                </div>
              </div>
              <Text_14_300_EEEEEE className="text-center">
                Please enter the Bud API key to access the playground
              </Text_14_300_EEEEEE>
            </div>

            <Form
              feedbackIcons={({ status, errors, warnings }) => {
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
                    value={key}
                    onPressEnter={() => handleAdd()}
                    onChange={(e) => setKey(e.target.value)}
                  />
                </div>
              </Form.Item>
              <PrimaryButton
                type="click"
                classNames="w-[100%] mt-[1.6rem]"
                onClick={() => handleAdd()}
              >
                Login
              </PrimaryButton>
            </Form>
            {isInvalidApiKey && <div className="text-center text-[#ec7575] text-[0.75rem] bg-[#ec75751a] border border-[#ec7575] rounded-[6px] p-[.5rem] mt-[3rem]">
              Invalid API Key
            </div>}
          </div>
        </div>
      </div>
    </div>
    );
}
