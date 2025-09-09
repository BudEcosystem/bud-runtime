import React, { useState } from "react";
import Image from "next/image";
import {
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/button";
import { Icon } from "@iconify/react";
import { useAuthNavigation } from "@/context/authContext";
import { motion } from "framer-motion";
import { getChromeColor } from "@/utils/getChromeColor";

type ContactAdminKeyProps = {
  onSubmit: (formData: string) => void;
};

const ContactAdmin = ({ onSubmit }: ContactAdminKeyProps) => {
  const { authError, setAuthError, setActivePage } = useAuthNavigation();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const [isValid, setIsValid] = useState(true);
  const [formData, setFormData] = useState<{ [key: string]: string }>({});
  const [isTouched, setIsTouched] = useState(false); // Add state for tracking touch
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
      <div className="mb-[.9rem] flex items-center justify-center">
        <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] mr-[.5rem]">
          Reset Password
        </Text_32_500_FFFFFF>
        <div className="text-3xl">🤝</div>
      </div>
      <Text_12_400_B3B3B3 className="text-center leading-[1.1rem]">
        New password will be sent to the email ID.
      </Text_12_400_B3B3B3>
      <div className="flex items-center justify-center flex-col mb-3 mx-auto w-full">
        <form onSubmit={submit} className="w-[76.6%] mt-[2em]">
          <div className="mb-[1.8rem]">
            <div className="relative">
              <span className="absolute px-1 bg-bud-bg-primary top-[-.4rem] left-2 inline-block tracking-[.035rem] z-10 text-xs font-light text-bud-text-muted">
                Email
              </span>
            </div>
            <input
              type="email"
              placeholder="Enter email"
              value={formData["email"] ?? ""}
              onChange={(e) => handleChange("email", e.target.value)}
              onBlur={handleBlur}
              className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-bud-text-primary placeholder:text-bud-text-disabled font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${showWarning ? "border-red-500" : "border-bud-border focus:border-bud-text-muted"}`}
            />
            {showWarning && (
              <div className="text-red-500 text-xs mt-2 flex items-center">
                <img
                  src="/icons/warning.svg"
                  alt="error"
                  className="w-4 h-4 mr-1"
                />
                {`Please enter your email`}
              </div>
            )}
            {!isValid && isTouched && formData.email && (
              <div className="mt-2">
                <div className="flex items-center bg-[#952F2F26] rounded-[6px] p-2">
                  <Icon
                    icon="ion:warning-outline"
                    className="text-[#E82E2E] mr-2 text-sm"
                  />
                  <div className="text-[#E82E2E] text-xs font-light">
                    Please provide a valid email
                  </div>
                </div>
              </div>
            )}
          </div>
          <PrimaryButton
            type="submit"
            classNames="w-[100%] mt-[1.6rem]"
            onClick={undefined}
          >
            Send
          </PrimaryButton>
        </form>
        <div
          className="flex items-center justify-center mt-[1.9rem] w-full cursor-pointer"
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
            className="ml-2 text-bud-text-primary tracking-[.035em]"
            onClick={() => {
              setAuthError("");
            }}
          >
            Back to Log In
          </Text_12_300_EEEEEE>
        </div>
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

export default ContactAdmin;
