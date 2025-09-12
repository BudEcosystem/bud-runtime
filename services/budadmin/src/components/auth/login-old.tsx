"use client";
import React, { useCallback, useEffect, useState } from "react";
import { Box, Button, Flex } from "@radix-ui/themes";
import {
  Text_12_300_EEEEEE,
  Text_12_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";
import { Icon } from "@iconify/react";
import { useAuthNavigation } from "src/context/appContext";
import * as Form from "@radix-ui/react-form";
import { CheckBoxInput } from "../ui/input";
import { useShortCut } from "../../hooks/useShortCut";

type LoginPageModalProps = {
  onSubmit: (formData: { [key: string]: string }) => void;
};

const LoginPage = ({ onSubmit }: LoginPageModalProps) => {
  const { setActivePage } = useAuthNavigation();
  const [formData, setFormData] = useState<{ [key: string]: string }>({});
  const [passwordError, setPasswordError] = useState("");
  const [isShow, setIsShow] = useState(false);
  const [isRememberCheck, setIsRememberCheck] = useState(false);
  const [isEmailValid, setIsEmailValid] = useState(true);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const validateForm = useCallback(() => {
    const passwordValid = formData["password"]?.length >= 8;
    const emailValid = emailRegex.test(formData["email"] || "");

    setPasswordError(
      formData["password"] && !passwordValid
        ? "Password must be at least 8 characters long"
        : "",
    );
    setIsEmailValid(!formData["email"] || emailValid);
  }, [formData, emailRegex]);

  useEffect(() => {
    if (isSubmitted) {
      validateForm();
    }
  }, [formData, isSubmitted, validateForm]);

  const handleLogin = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    setIsSubmitted(true);
    validateForm();
    if (isEmailValid && !passwordError) {
      onSubmit(formData);
    }
  };

  const handleChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  // Validate onBlur (focus out) event for email and password fields
  const handleBlur = () => {
    validateForm();
  };

  return (
    <Flex
      className="w-[70%] h-full open-sans mt-[-1rem]"
      direction="column"
      justify="center"
      align="center"
    >
      <Box className="mb-8">
        <Flex align="center" justify={"center"} className="mb-2">
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
        </Flex>
        <Text_12_400_B3B3B3 className="text-center">
          Enter your email and password to access your account
        </Text_12_400_B3B3B3>
      </Box>

      <Form.Root className="w-[76.6%] mt-[1.6em]" onSubmit={handleLogin}>
        <Form.Field className="mb-[1.4rem]" name="email">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem]">
              Email
            </Text_12_300_EEEEEE>
          </div>
          <Form.Control asChild>
            <input
              placeholder="Enter email"
              className={`h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border rounded-[6px] py-2 px-2.5 ${
                formData["email"] ? "border-[#CFCFCF]" : "border-[#757575]"
              }`}
              type="email"
              value={formData["email"] || ""}
              onChange={(e) => handleChange("email", e.target.value)}
              onBlur={handleBlur} // Trigger validation on blur
              required
            />
          </Form.Control>

          {/* Show error message only if input is not empty and invalid */}
          {formData["email"] && !isEmailValid && (
            <Form.Message asChild className="mt-2">
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"center"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 text-sm"
                />
                <div className="text-[#E82E2E] text-xs font-light">
                  Please provide a valid email
                </div>
              </Flex>
            </Form.Message>
          )}
        </Form.Field>

        <Form.Field name="password" className="mb-[.8rem]">
          <div
            className={`flex items-center border ${
              formData["password"] ? "border-[#CFCFCF]" : "border-[#757575]"
            } rounded-[6px] relative hover:bg-white hover:bg-opacity-[3%]`}
          >
            <div className="">
              <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem]">
                Password
              </Text_12_300_EEEEEE>
            </div>
            <Form.Control asChild>
              <input
                placeholder="Enter password"
                className="h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none bg-transparent py-2 px-2.5 flex-grow rounded-l-[5px]"
                type={isShow ? "text" : "password"}
                value={formData["password"] || ""}
                onChange={(e) => handleChange("password", e.target.value)}
                onBlur={handleBlur} // Trigger validation on blur
                required
              />
            </Form.Control>
            <div className="w-1/5 flex justify-center items-center">
              <Icon
                icon={isShow ? "ph:eye" : "clarity:eye-hide-line"}
                className="text-[#808080] cursor-pointer"
                onClick={() => setIsShow(!isShow)}
              />
            </div>
          </div>

          {/* Show password error only if input is not empty and invalid */}
          {formData["password"] && passwordError && (
            <Flex
              className="bg-[#952F2F26] rounded-[6px] p-2 mt-2"
              align={"center"}
            >
              <Icon
                icon="ion:warning-outline"
                className="text-[#E82E2E] mr-2 text-sm"
              />
              <div className="text-[#E82E2E] text-xs font-light">
                {passwordError}
              </div>
            </Flex>
          )}
        </Form.Field>

        <div className="flex items-center">
          <label
            htmlFor="isRemember"
            className="flex items-center cursor-pointer"
            onClick={() => setIsRememberCheck(!isRememberCheck)}
          >
            <CheckBoxInput
              id="isRemember"
              defaultCheck={false}
              checkedChange={isRememberCheck}
              onClick={() => setIsRememberCheck(!isRememberCheck)}
            />
            <Text_12_400_808080 className="ml-[.45rem] tracking-[.01rem] cursor-pointer select-none">
              Remember me
            </Text_12_400_808080>
          </label>
        </div>

        <Form.Submit asChild>
          <ButtonInput
            type="submit"
            className="text-[#FFFFFF] w-full box-border focus:outline-none rounded-md cursor-pointer mt-[2.1rem] h-[2rem]"
            onClick={null}
          >
            Login
          </ButtonInput>
        </Form.Submit>
      </Form.Root>

      <Flex justify={"center"} className="mt-[2.2rem]">
        <Text_12_400_808080 className="mr-2">
          Forgot password?
        </Text_12_400_808080>
        <Text_12_400_EEEEEE
          className="cursor-pointer"
          onClick={() => {
            setActivePage(4);
          }}
        >
          Contact Admin
        </Text_12_400_EEEEEE>
      </Flex>
    </Flex>
  );
};

export default LoginPage;
