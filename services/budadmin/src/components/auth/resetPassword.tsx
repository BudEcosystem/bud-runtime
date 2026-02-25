/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useEffect, useState } from "react";
import { Flex, Box } from "@radix-ui/themes";
import Image from "next/image";

import {
  Text_12_300_EEEEEE,
  Text_12_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
  Text_32_600_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";
import { Icon } from "@iconify/react";
import * as Form from "@radix-ui/react-form";
import { useAuthNavigation } from "src/context/appContext";
import { motion } from "framer-motion";
import { getChromeColor } from "../ui/bud/dataEntry/TagsInputData";
import { useUser } from "src/stores/useUser";

type ResetPasswordProps = {
  onSubmit: (formData: string) => void;
};

const ResetPasswordPage = ({ onSubmit }: ResetPasswordProps) => {
  const { getUser, user } = useUser();
  const { authError } = useAuthNavigation();
  const [isNewIsShow, setNewIsShow] = useState(false);
  const [isConfIsShow, setConfIsShow] = useState(false);
  const [isRememberCheck, setIsRememberCheck] = useState(false);

  const [rePassword, setRePassword] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [userDetails, setUserDetails] = useState<any>();
  const [isTouched, setIsTouched] = useState({
    rePassword: false,
    password: false,
  });

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    getUser();
  }, [getUser]);

  const passwordRegex =
    /^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$/;

  const handleSubmitPassword = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    onSubmit(rePassword);
  };

  const handleBlur = (field: any) => {
    setIsTouched({ ...isTouched, [field]: true });
  };

  if (!mounted) {
    // Return null or skeleton UI during SSR
    return null;
  }

  return (
    <>
      <Flex justify={"center"} align={"center"} className="mb-[.8rem]">
        <Text_32_500_FFFFFF className="tracking-[.02em] leading-[35px] text-center !font-[400]">
          Reset your password
        </Text_32_500_FFFFFF>
        <Image
          src="/gifs/finger-down-emoji.gif"
          width={40}
          height={40}
          style={{ width: "40px", height: "auto !important" }}
          alt=""
        />
      </Flex>
      <Text_12_400_B3B3B3 className="text-center">
        Please reset your password
      </Text_12_400_B3B3B3>
      <Flex
        align="center"
        justify={"center"}
        className="mb-3 mt-[1.55rem] mx-auto w-full"
      >
        <Form.Root
          className="w-[76.6%] mt-[2em]"
          onSubmit={handleSubmitPassword}
        >
          <Form.Field name="password" className="mb-5">
            <Box
              className={`flex items-center border ${
                password ? "border-[#CFCFCF]" : "border-[#757575]"
              } rounded-[5px] relative hover:bg-white hover:bg-opacity-[3%]`}
            >
              <Box className="">
                <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem]">
                  New Password
                </Text_12_300_EEEEEE>
              </Box>
              <Form.Control asChild>
                <input
                  placeholder="Enter password"
                  className={`h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none bg-transparent  py-2 px-2.5 flex-grow rounded-l-[5px]`}
                  type={isNewIsShow ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => handleBlur("password")}
                />
              </Form.Control>
              <Box className="w-1/5 flex justify-center items-center">
                <Icon
                  icon={isNewIsShow ? "ph:eye" : "clarity:eye-hide-line"}
                  className="text-[#808080] cursor-pointer"
                  onClick={() => setNewIsShow(!isNewIsShow)}
                />
              </Box>
            </Box>
            <Form.Message asChild className="mt-2" match="valueMissing">
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"center"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 text-sm"
                />
                <Box className="text-[#E82E2E] text-xs font-light">
                  Please enter your password
                </Box>
              </Flex>
            </Form.Message>
            <Form.Message
              asChild
              className="mt-2"
              match={(value, formData) => !passwordRegex.test(value)}
            >
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"start"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 mt-[.2rem] text-sm"
                />
                <Box className="text-[#E82E2E] text-xs font-light max-w-[90%]">
                  Password must be at least 8 characters long, contain at least
                  one number, one letter, and one special character without any
                  spaces
                </Box>
              </Flex>
            </Form.Message>
          </Form.Field>
          <Form.Field name="rePassword" className="mb-[.9rem]">
            <Box
              className={`flex items-center border ${
                rePassword ? "border-[#CFCFCF]" : "border-[#757575]"
              } rounded-[5px] relative hover:bg-white hover:bg-opacity-[3%]`}
            >
              <Box className="">
                <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem]">
                  Confirm Password
                </Text_12_300_EEEEEE>
              </Box>
              <Form.Control asChild>
                <input
                  placeholder="Re enter password"
                  className={`h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none bg-transparent  py-2 px-2.5 flex-grow rounded-l-[5px]`}
                  type={isConfIsShow ? "text" : "password"}
                  required
                  value={rePassword}
                  onChange={(e) => setRePassword(e.target.value)}
                  onBlur={() => handleBlur("rePassword")}
                />
              </Form.Control>
              <Box className="w-1/5 flex justify-center items-center">
                <Icon
                  icon={isConfIsShow ? "ph:eye" : "clarity:eye-hide-line"}
                  className="text-[#808080] cursor-pointer"
                  onClick={() => setConfIsShow(!isConfIsShow)}
                />
              </Box>
            </Box>
            <Form.Message asChild className="mt-2" match="valueMissing">
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"center"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 text-sm"
                />
                <Box className="text-[#E82E2E] text-xs font-light">
                  Please re-enter your password
                </Box>
              </Flex>
            </Form.Message>
            <Form.Message
              asChild
              className="mt-2"
              match={(value, formData) => value.length < 8}
            >
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"center"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 text-sm"
                />
                <Box className="text-[#E82E2E] text-xs font-light">
                  Password must be at least 8 characters long
                </Box>
              </Flex>
            </Form.Message>
            <Form.Message
              asChild
              className="mt-2"
              match={(value, formData) => value !== password}
            >
              <Flex
                className="bg-[#952F2F26] rounded-[6px] p-2"
                align={"center"}
              >
                <Icon
                  icon="ion:warning-outline"
                  className="text-[#E82E2E] mr-2 text-sm"
                />
                <Box className="text-[#E82E2E] text-xs font-light">
                  Passwords do not match
                </Box>
              </Flex>
            </Form.Message>
          </Form.Field>
          <Box className="flex items-center mb-[2.1rem]">
            <input type="checkbox" id="isRemember" className="mr-1" hidden />
            <label
              htmlFor="isRemember"
              className="flex items-center"
              onClick={() => setIsRememberCheck(!isRememberCheck)}
            >
              <Image
                src={
                  isRememberCheck
                    ? "/icons/checked.svg"
                    : "/icons/unchecked.svg"
                }
                width={14}
                height={14}
                className="text-gray-50"
                alt=""
              />
              <Text_12_400_808080 className="ml-2 cursor-default select-none">
                Remember me
              </Text_12_400_808080>
            </label>
          </Box>
          <Form.Submit asChild>
            <ButtonInput
              className={`loginButton text-[#FFFFFF] w-full box-border focus:outline-none rounded-md cursor-pointer h-[2rem]`}
              onClick={null}
            >
              Update
            </ButtonInput>
          </Form.Submit>
        </Form.Root>
      </Flex>
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
            {typeof window !== "undefined" && !navigator.onLine
              ? "No internet connection"
              : authError.includes("Cannot read properties")
                ? "Something went wrong, please try again later."
                : authError}
          </Text_12_400_EEEEEE>
        </motion.div>
      )}
    </>
  );
};

export default ResetPasswordPage;
