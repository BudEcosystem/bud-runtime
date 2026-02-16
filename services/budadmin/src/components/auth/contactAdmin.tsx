import React, { useState } from "react";
import { Flex } from "@radix-ui/themes";
import Image from "next/image";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import * as Form from "@radix-ui/react-form";
import { ButtonInput } from "@/components/ui/button";
import { Icon } from "@iconify/react";
import { useAuthNavigation } from "src/context/appContext";
import { motion } from "framer-motion";
import { getChromeColor } from "../ui/bud/dataEntry/TagsInputData";

type ContactAdminKeyProps = {
  onSubmit: (formData: string) => void;
};

const ContactAdmin = ({ onSubmit }: ContactAdminKeyProps) => {
  const { authError, setAuthError } = useAuthNavigation();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const [isValid, setIsValid] = useState(true);
  const [formData, setFormData] = useState<{ [key: string]: string }>({});
  const [isTouched, setIsTouched] = useState(false); // Add state for tracking touch
  const { setActivePage } = useAuthNavigation();
  const [showWarning, setShowWarning] = useState(false);

  const handleChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (name === "email") {
      setShowWarning(false);
      setIsValid(emailRegex.test(value));
    }
  };

  const handleBlur = () => {
    setIsTouched(true); // Set as touched when the input loses focus
  };

  const submit = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    setIsTouched(true); // Set as touched on form submit
    if (!formData.email) {
      setShowWarning(true);
    } else {
      setShowWarning(false);
      onSubmit(formData.email);
    }
  };

  return (
    <>
      <Flex justify={"center"} align={"center"} className="mb-[.9rem]">
        <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] mr-[.5rem]">
          Reset Password
        </Text_32_500_FFFFFF>
        <div className="text-3xl">🤝</div>
      </Flex>
      <Text_12_400_B3B3B3 className="text-center leading-[1.1rem]">
        New password will be sent to the email ID.
      </Text_12_400_B3B3B3>
      <Flex
        align="center"
        justify={"center"}
        direction={"column"}
        className="mb-3 mx-auto w-full"
      >
        <Form.Root className="w-[76.6%] mt-[3.4rem]" onSubmit={submit}>
          <Form.Field className="mb-[1.4rem]" name="email">
            <div className="relative">
              <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block ">
                Email
              </Text_12_300_EEEEEE>
            </div>
            <Form.Control asChild>
              <input
                placeholder="Enter email"
                className={`${
                  formData["email"] ? "border-[#CFCFCF]" : "border-[#757575]"
                } h-10 w-full placeholder:text-xs text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border rounded-[5px] py-2 px-2.5`}
                type="email"
                value={formData["email"]}
                onChange={(e) => handleChange("email", e.target.value)}
                onBlur={handleBlur} // Trigger touch on blur
              />
            </Form.Control>
            {showWarning && (
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
                    Please enter your email
                  </div>
                </Flex>
              </Form.Message>
            )}

            {!isValid && isTouched && formData.email && (
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
          <Form.Submit asChild>
            <ButtonInput
              className={`loginButton text-[#FFFFFF] w-full box-border focus:outline-none rounded-md cursor-pointer h-[2rem]`}
              onClick={undefined}
            >
              Send
            </ButtonInput>
          </Form.Submit>
        </Form.Root>
        <Flex
          className="mt-[1.9rem] cursor-pointer"
          align={"center"}
          justify={"center"}
          onClick={() => {
            setActivePage(1);
          }}
        >
          <Image
            src="/icons/left-circle-navigation.svg"
            alt="right-arrow-circle"
            width={25}
            height={25}
            className="!w-[1.37rem] !h-[1.35rem]"
          />
          <Text_12_300_EEEEEE
            className="ml-2 tracking-[.035em]"
            onClick={() => {
              setAuthError("");
            }}
          >
            Back to Log In
          </Text_12_300_EEEEEE>
        </Flex>
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

export default ContactAdmin;
