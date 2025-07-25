/* eslint-disable jsx-a11y/alt-text */
/* eslint-disable @next/next/no-img-element */
/* eslint-disable react/no-unescaped-entities */
"use client";
import React from "react";
import { Box, Flex } from "@radix-ui/themes";
import Image from "next/image";

import {
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_400_FFFFFF,
  Text_32_600_FFFFFF,
} from "@/components/ui/text";

type Props = {};

const RequestSent = (props: Props) => {
  return (
    <>
      <Box className="w-[76.6%]">
        <Image src="/gifs/up-hands.gif" alt="" className="w-[9.5rem] h-auto mb-[3.2rem]" />
        <Text_32_400_FFFFFF className="tracking-[.02em] leading-[100%] text-center !font-thin mb-[1.2rem]">
          Request Sent
        </Text_32_400_FFFFFF>
        <Text_12_400_B3B3B3 className="text-center leading-[1.125rem]">
          Your password reset request has been sent. The admin will contact you
          shortly.
        </Text_12_400_B3B3B3>
        <Flex align="center" justify={"center"} className="mb-3 mx-auto w-full">
          <Flex className="mt-[4.1rem]" align={"center"} justify={"center"}>
            <Image
              src="/icons/left-circle-navigation.svg"
              alt="right-arrow-circle"
            />
            <Text_12_400_EEEEEE className="ml-2 cursor-pointer tracking-[.01rem]">
              Back to Log In
            </Text_12_400_EEEEEE>
          </Flex>
        </Flex>
      </Box>
    </>
  );
};

export default RequestSent;
