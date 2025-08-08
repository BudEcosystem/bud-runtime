import React from "react";
import { Flex, Box } from "@radix-ui/themes";

interface DrawerCardProps {
  children?: React.ReactNode;
  classNames?: any
}

function DrawerCard({ children, classNames }: DrawerCardProps) {
  return (
    <Box className={`px-[1.4rem] py-[.9rem] rounded-es-lg rounded-ee-lg pb-4 ${classNames}`}>
      {children}
    </Box>
  );
}

export default DrawerCard;
