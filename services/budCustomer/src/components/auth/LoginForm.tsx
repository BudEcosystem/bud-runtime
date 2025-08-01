"use client";
import React, { useEffect, useState } from "react";
import {
  Text_12_300_EEEEEE,
  Text_12_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import { useAuthNavigation } from "@/context/authContext";
import { CheckBoxInput } from "@/components/ui/input";
import { PrimaryButton } from "@/components/ui/button";
import { motion } from "framer-motion";
import { getChromeColor } from "@/utils/getChromeColor";

type LoginPageModalProps = {
  onSubmit: (formData: { [key: string]: string }) => void;
};

const LoginForm = ({ onSubmit }: LoginPageModalProps) => {
  const { setActivePage, authError, setAuthError } = useAuthNavigation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isShow, setIsShow] = useState(false);
  const [isRememberCheck, setIsRememberCheck] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [submittable, setSubmittable] = useState(false);
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    // Check if form is submittable
    const isEmailValid = email.length >= 3 && emailRegex.test(email);
    const isPasswordValid = password.length >= 8;
    setSubmittable(isEmailValid && isPasswordValid);
  }, [email, password, emailRegex]);

  const validateEmail = (value: string) => {
    if (!value) {
      setEmailError('Please input your email!');
      return false;
    }
    if (value.length < 3) {
      return true; // Don't show error for short input
    }
    if (!emailRegex.test(value)) {
      setEmailError('Please enter a valid email');
      return false;
    }
    setEmailError('');
    return true;
  };

  const validatePassword = (value: string) => {
    if (!value) {
      setPasswordError('Please input your password!');
      return false;
    }
    if (value.length < 8) {
      setPasswordError('Password must be at least 8 characters long!');
      return false;
    }
    setPasswordError('');
    return true;
  };

  const handleLogin = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    if (!submittable) return;
    onSubmit({ email, password });
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    if (value.length >= 3) {
      validateEmail(value);
    } else {
      setEmailError('');
    }
    if (!value) {
      setAuthError('');
    }
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPassword(value);
    if (value.length >= 8) {
      validatePassword(value);
    } else if (value.length > 0) {
      setPasswordError('Password must be at least 8 characters long!');
    } else {
      setPasswordError('');
    }
    if (!value) {
      setAuthError('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleLogin(e as any);
    }
  };

  if (!mounted) {
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

      <form
        onSubmit={handleLogin}
        className="w-[76.6%] mt-[1.6em]"
      >
        <div className="mb-[1.8rem]">
          <div className="relative">
            <Text_12_300_EEEEEE className="absolute px-1 bg-black -top-1 left-2 inline-block tracking-[.035rem] z-10">
              Email
            </Text_12_300_EEEEEE>
          </div>
          <input
            type="email"
            placeholder="Enter email"
            value={email}
            onChange={handleEmailChange}
            onBlur={() => validateEmail(email)}
            className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none border rounded-[6px] pt-[.8rem] pb-[.53rem] px-3 bg-transparent
              ${emailError ? 'border-red-500' : 'border-gray-600 focus:border-gray-400'}`}
          />
          {emailError && (
            <div className="text-red-500 text-xs mt-1 flex items-center">
              <img src="/icons/warning.svg" alt="error" className="w-4 h-4 mr-1" />
              {emailError}
            </div>
          )}
        </div>

        <div className="mb-[1rem]">
          <div className="flex items-center border rounded-[6px] relative !bg-[transparent]">
            <div className="">
              <Text_12_300_EEEEEE className="absolute px-1.5 bg-black -top-1.5 left-1.5 inline-block tracking-[.035rem] z-10">
                Password
              </Text_12_300_EEEEEE>
            </div>
            <input
              type={isShow ? "text" : "password"}
              placeholder="Enter password"
              value={password}
              onChange={handlePasswordChange}
              onKeyDown={handleKeyDown}
              autoComplete="current-password"
              className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-[#EEEEEE] placeholder:text-[#808080] font-light outline-none !bg-[transparent] border-none rounded-[6px] pt-[.8rem] pb-[.53rem] px-3`}
            />
            <button
              type="button"
              onClick={() => setIsShow(!isShow)}
              className="text-[#808080] cursor-pointer pr-3"
            >
              {isShow ? "👁️" : "🙈"}
            </button>
          </div>
          {passwordError && (
            <div className="text-red-500 text-xs mt-1 flex items-center">
              <img src="/icons/warning.svg" alt="error" className="w-4 h-4 mr-1" />
              {passwordError}
            </div>
          )}
        </div>

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

        <PrimaryButton
          type="submit"
          classNames="w-[100%] mt-[1.6rem]"
          disabled={!submittable}
        >
          Login
        </PrimaryButton>
      </form>

      <div className="mt-[2.2rem] flex justify-center">
        <Text_12_400_EEEEEE
          className="cursor-pointer"
          onClick={() => {
            setActivePage(4);
          }}
        >
          Forgot password?
        </Text_12_400_EEEEEE>
      </div>

      {authError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeIn" }}
          className="border-[1px] border-[#EC7575] rounded-[6px] px-[.5rem] py-[1rem] flex justify-center items-center w-[76.6%] mt-[1.5rem]"
          style={{
            backgroundColor: getChromeColor("#EC7575"),
          }}
        >
          <Text_12_400_EEEEEE className="text-[#EC7575]">
            {authError.includes('Cannot read properties') ? 'Something went wrong, please try again later.' : authError}
          </Text_12_400_EEEEEE>
        </motion.div>
      )}
    </>
  );
};

export default LoginForm;
