// components/CommonLoader.tsx
import React from "react";
import { Box, Spinner } from "@radix-ui/themes";
import Image from "next/image";
// Use direct path for public assets in Next.js
const loaderIcn = "/icons/loader.gif";

interface LoaderProps {
  isLoading: boolean;
}

const CommonLoader: React.FC<LoaderProps> = ({ isLoading }) => {
  return isLoading ? (
    <Box className="z-[1000] fixed top-0 left-0 w-screen h-screen flex justify-center items-center backdrop-blur-[2px]">
      {/* <Spinner size="3" className="w-[20px] h-[20px]" /> */}
      <Image
        width={20}
        className="w-[20px] h-[20px]"
        src={loaderIcn}
        alt="Logo"
      />
    </Box>
  ) : null;
};

export default CommonLoader;
