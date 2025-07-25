import { Box, Flex } from "@radix-ui/themes";
import React from "react";
import Image from "next/image";
import { Heading_26_600_FFFFFF, Text_14_400_787B83 } from "../text";
import { ButtonInput } from "../button";
import noAccessIcn from "./../../../../public/icons/noaccess.png";

interface noAccessProps {
  textMessage?: any,
  classNames?: string
}
const NoAccess: React.FC<noAccessProps> = ({ textMessage, classNames }) => {

  return (
    <Flex justify="center" align="center" className={`w-full h-[80%] ${classNames}`}>
      <Box>
        <Flex justify="center" className="mb-[1em]">
          <Image
            width={100}
            className="w-[2.25em] h-[2.25em]"
            src={noAccessIcn}
            alt="Logo"
          />
        </Flex>
        <Box>
          {textMessage && (
            <Box>
              <Text_14_400_787B83 >{textMessage}</Text_14_400_787B83>
            </Box>
          )}
        </Box>
      </Box>
    </Flex>
  );
};

export default NoAccess;
