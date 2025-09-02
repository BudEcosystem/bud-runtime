/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useState, useEffect } from "react";
import { Flex, Box } from "@radix-ui/themes";
import Image from "next/image";

import {
  Text_12_300_EEEEEE,
  Text_12_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_400_FFFFFF,
  Text_32_500_FFFFFF,
  Text_32_600_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";
import { Icon } from "@iconify/react";
import * as Form from "@radix-ui/react-form";
import { useRouter } from "next/navigation";
import { useAuthNavigation, useLoader } from "src/context/appContext";
import { AppRequest } from "./../../pages/api/requests";

type HuggingfaceKeyProps = {
  onSubmit: (formData: string) => void;
};

const HuggingfaceKeyPage = ({ onSubmit }: HuggingfaceKeyProps) => {
  const [mounted, setMounted] = useState(false);
  const { isLoading, showLoader, hideLoader } = useLoader();
  const [huggKey, setHuggKey] = useState("");
  const [isNewIsShow, setNewIsShow] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

  const addHuggingfaceKey = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    onSubmit(huggKey);
  };

  const validateUser = async () => {
    showLoader();
    try {
      const response: any = await AppRequest.Patch("/users/onboard");
      hideLoader();
      const data = response.data;
      if (data.success) {
        router.push("/dashboard");
      }
    } catch (error) {
      hideLoader();
    }
  };

  if (!mounted) {
    // Return null or skeleton UI during SSR
    return null;
  }

  return (
    <>
      <Flex justify={"center"} align={"center"}>
        <Text_32_400_FFFFFF className="tracking-[.02em] leading-[100%] text-center mr-[.2rem]">
          Add Huggingface key
        </Text_32_400_FFFFFF>
        <Image
          alt=""
          src="/gifs/smiley.gif"
          width={40}
          height={40}
          style={{ width: "2.6rem", height: "auto" }}
        />
      </Flex>
      <Text_12_400_B3B3B3 className="text-center mt-[.8rem]">
        Please add your Huggingface key
      </Text_12_400_B3B3B3>
      <Flex
        align="center"
        justify={"center"}
        className="mb-3 mx-auto w-full mt-[1.5rem]"
      >
        <Form.Root className="w-[76.6%] mt-[2em]" onSubmit={addHuggingfaceKey}>
          <Form.Field name="huggingfaceKey">
            <Box
              className={`flex items-center border ${
                huggKey ? "border-[#CFCFCF]" : "border-[#757575]"
              } rounded-[5px] relative hover:bg-white hover:bg-opacity-[3%]`}
            >
              <Box className="">
                <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem]">
                  Huggingface key
                </Text_12_300_EEEEEE>
              </Box>
              <Form.Control asChild>
                <input
                  placeholder="Enter key"
                  className={`h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none bg-transparent  py-2 px-2.5 flex-grow rounded-l-[5px]`}
                  type={isNewIsShow ? "text" : "password"}
                  required
                  value={huggKey}
                  onChange={(e) => setHuggKey(e.target.value)}
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
                  Please enter your huggingface key
                </Box>
              </Flex>
            </Form.Message>
          </Form.Field>
          <Form.Submit asChild>
            <ButtonInput
              className={`loginButton text-[#FFFFFF] w-full box-border focus:outline-none rounded-md cursor-pointer mt-[1.9rem] h-[2rem]`}
              onClick={null}
            >
              Add
            </ButtonInput>
          </Form.Submit>
          <Flex
            className="mt-8 cursor-pointer"
            align={"center"}
            justify={"center"}
            onClick={validateUser}
          >
            <Text_12_400_EEEEEE className="mr-2 cursor-pointer">
              Skip
            </Text_12_400_EEEEEE>
            <Image
              src="/icons/right-circle.svg"
              width={15}
              height={15}
              alt="right-arrow-circle"
            />
          </Flex>
        </Form.Root>
      </Flex>
    </>
  );
};

export default HuggingfaceKeyPage;
