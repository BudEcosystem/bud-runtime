"use client";
import React, { useEffect, useState } from "react";
import {
  Text_12_300_EEEEEE,
  Text_12_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import { Icon } from "@iconify/react";
import { useAuthNavigation } from "src/context/appContext";
import { CheckBoxInput } from "../ui/input";
import { PrimaryButton } from "../ui/bud/form/Buttons";
import { Form, Image, Input } from "antd";
import { getChromeColor } from "../ui/bud/dataEntry/TagsInputData";
import { motion } from "framer-motion";

type LoginPageModalProps = {
  onSubmit: (formData: { [key: string]: string }) => void;
};

const LoginPage = ({ onSubmit }: LoginPageModalProps) => {
  const [form] = Form.useForm();
  const { setActivePage, authError, setAuthError } = useAuthNavigation();
  const [isShow, setIsShow] = useState(false);
  const [isRememberCheck, setIsRememberCheck] = useState(false);
  const [submittable, setSubmittable] = useState(false);
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  // Watch all values
  const values = Form.useWatch([], form);
  useEffect(() => {
    form
      .validateFields({
        validateOnly: true,
        // dirty: true,
      })
      .then((result) => {
        setSubmittable(true);
      })
      .catch(() => setSubmittable(false));
  }, [form, values]);

  const handleLogin = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    if (!submittable) return;
    const formData = form.getFieldsValue();
    if (isRememberCheck) {
      formData.remember_me = true;
    }
    onSubmit(formData);
  };

  useEffect(() => {
    form.setFieldsValue({
      email: "",
      password: "",
    });
  }, [form]);

  if (!mounted) {
    // Return null or skeleton UI during SSR
    return null;
  }

  return (
    <>
      <div className="mb-8">
        <div className="flex justify-center items-center mb-[.9rem]">
          <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center">
            Hey, hello
          </Text_32_500_FFFFFF>
          <video
            src="/webm/wave.webm"
            autoPlay
            loop
            muted
            playsInline
            className="w-[45px] h-auto mb-1 2xl:w-12"
          />
        </div>
        <Text_12_400_B3B3B3 className="text-center">
          Enter your email and password to access your account
        </Text_12_400_B3B3B3>
      </div>

      <Form
        onFinish={(e) => {
          if (isRememberCheck) {
            e.remember_me = true;
          }
          onSubmit(e);
        }}
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
        className="w-[76.6%] mt-[1.6em]"
        form={form}
      >
        <Form.Item
          hasFeedback
          className="mb-[1.8rem]"
          name="email"
          // validateDebounce={500}
          validateTrigger={["onBlur"]}
          rules={[
            // {
            //   required: true,
            //   message: "Please input your email!",
            // },
            // {
            //   type: "email",
            //   message: "Please enter a valid email",
            // },
            {
              validator: (_, value) => {
                if (!value) {
                  return Promise.reject("Please input your email!");
                }
                if (value.length < 3) {
                  // Don't show error if fewer than 3 characters (return resolved promise)
                  return Promise.resolve();
                }
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                  return Promise.reject("Please enter a valid email");
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <div>
            <div className="relative">
              <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
                Email
              </Text_12_300_EEEEEE>
            </div>
            <Input
              placeholder="Enter email"
              className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem]`}
              onChange={(e) => {
                const value = e.target.value;
                form.setFieldsValue({ email: value });
                if (value.length >= 3) {
                  form.validateFields(["email"]);
                }
                // form.validateFields(["email"]);
                if (!value) {
                  setAuthError("");
                }
              }}
              onBlur={() => {
                form.validateFields(["email"]);
              }}
            />
          </div>
        </Form.Item>

        <Form.Item
          hasFeedback
          name="password"
          className="mb-[1rem]"
          // validateDebounce={500}
          validateTrigger="onChange"
          rules={[
            // {
            //   required: true,
            //   message: "Please input your password!",
            // },
            // {
            //   min: 8,
            //   message: "Password must be at least 8 characters long",
            // },
            {
              validator: (_, value) => {
                if (!value) {
                  return Promise.reject("Please input your password!");
                }
                if (value.length < 8) {
                  // Don't show error if fewer than 3 characters (return resolved promise)
                  return Promise.reject(
                    "Password must be at least 8 characters long!",
                  );
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <div
            className={`flex items-center border rounded-[6px] relative !bg-[transparent]`}
          >
            <div className="">
              <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem] z-10">
                Password
              </Text_12_300_EEEEEE>
            </div>
            <Input
              placeholder="Enter password"
              className={`passwordField h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE]  placeholder:text-[#808080] font-light outline-none !bg-[transparent] border rounded-[6px] pt-[.8rem] pb-[.53rem]`}
              type={isShow ? "text" : "password"}
              classNames={{
                input: "rounded-l-[5px] border-none!",
              }}
              autoComplete="no-fill"
              variant="borderless"
              suffix={
                <Icon
                  icon={isShow ? "ph:eye" : "clarity:eye-hide-line"}
                  className="text-[#808080] cursor-pointer"
                  onClick={() => setIsShow(!isShow)}
                />
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  form.submit(); // This will trigger onFinish
                }
              }}
              onChange={(e) => {
                const value = e.target.value;
                if (value.length >= 8) {
                  form.validateFields(["password"]);
                }
                if (!value) {
                  setAuthError("");
                }
              }}
            />
          </div>
        </Form.Item>

        <div className="flex items-center">
          <label
            htmlFor="isRemember"
            className="flex items-center cursor-pointer"
          >
            <CheckBoxInput
              id="isRemember"
              defaultCheck={false}
              checkedChange={isRememberCheck}
              onCheckedChange={(checked) => setIsRememberCheck(checked)}
            />
            <Text_12_400_808080 className="ml-[.45rem] tracking-[.01rem] cursor-pointer select-none">
              Remember me
            </Text_12_400_808080>
          </label>
        </div>

        <PrimaryButton
          type="primary"
          classNames="w-[100%] mt-[1.6rem]"
          onClick={handleLogin}
        >
          Login
        </PrimaryButton>
      </Form>

      <div className="mt-[2.2rem] flex justify-center">
        <Text_12_400_EEEEEE
          className="cursor-pointer"
          onClick={() => {
            setActivePage(4);
          }}
        >
          Forgot password?
        </Text_12_400_EEEEEE>
        {/* <Text_12_400_EEEEEE
          className="cursor-pointer"
          onClick={() => {
            setActivePage(4);
          }}
        >
          Contact Admin
        </Text_12_400_EEEEEE> */}
      </div>
      {authError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} // Start slightly above and transparent
          animate={{ opacity: 1, y: 0 }} // Move down and appear
          transition={{ duration: 0.5, ease: "easeIn" }} // Smooth transition
          className="border-[1px] border-[#EC7575] rounded-[6px] px-[.5rem] py-[1rem] flex justify-center items-center w-[76.6%] mt-[1.5rem]"
          style={{
            backgroundColor: getChromeColor("#EC7575"),
          }}
        >
          <Text_12_400_EEEEEE className="text-[#EC7575]">
            {authError.includes("Cannot read properties")
              ? "Something went wrong, please try again later."
              : authError}
          </Text_12_400_EEEEEE>
        </motion.div>
      )}
    </>
  );
};

export default LoginPage;
