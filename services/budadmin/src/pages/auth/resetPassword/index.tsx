/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useEffect, useState } from "react";
import Image from "next/image";
import * as Form from "@radix-ui/react-form";
import { Box, Flex, Text } from "@radix-ui/themes";
import { useRouter } from "next/router";
import logoWhite from "./../../../../public/images/logoBud.png";
import { useLoader } from "./../../../context/appContext";
import { AppRequest } from "./../../api/requests";
import AuthLayout from "../layout";
import {
  Text_12_400_red,
  Text_13_300_FFFFFF,
  Text_24_500_FFFFFF,
} from "@/components/ui/text";
import { ButtonInput } from "@/components/ui/button";
import { successToast } from "@/components/toast";
import { useUser } from "src/stores/useUser";

export default function ResetPassword() {
  const { isLoading, showLoader, hideLoader } = useLoader();
  const [access_token, setAccessToken] = useState("");
  const [refresh_token, setRefreshToken] = useState("");
  const { user, getUser } = useUser();
  const router = useRouter();
  const [rePassword, setRePassword] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [rePasswordError, setRePasswordError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [isFormValid, setIsFormValid] = useState(false);
  const [isTouched, setIsTouched] = useState({
    rePassword: false,
    password: false,
  });

  useEffect(() => {
    const validateForm = () => {
      const rePasswordValid = rePassword.length >= 8;
      const passwordValid = password.length >= 8;
      const passwordsMatch = password === rePassword;

      setRePasswordError(
        rePasswordValid ? "" : "Password must be at least 8 characters long"
      );
      setPasswordError(
        passwordValid ? "" : "Password must be at least 8 characters long"
      );
      setError(
        rePassword.length > 0 && !passwordsMatch ? "Passwords do not match" : ""
      );
      setIsFormValid(rePasswordValid && passwordValid && passwordsMatch);
    };
    validateForm();
  }, [rePassword, password]);

  const handleSubmitPassword = async (e) => {
    e.preventDefault();
    showLoader();
    setError("");
    const payload = {
      password: rePassword,
    };
    try {
      const response = await AppRequest.Patch(`users/${user.id}`, payload);
      successToast(response.data.message);
      router.push("/login");
      localStorage.clear();
      hideLoader();
    } catch (error) {
      console.error("Login error:", error);
      setError("Something went wrong");
      hideLoader();
    }
  };

  const handleBlur = (field) => {
    setIsTouched({ ...isTouched, [field]: true });
  };

  useEffect(() => {
    getUser();
  }, []);

  return (
    <AuthLayout>
      <Flex
        className="w-full h-full bg-[#0f0f0f] border border-[#18191B] rounded-2xl overflow-hidden px-[23.4%]"
        direction="column"
        justify="center"
      >
        <Box className="w-[5.2em]">
          <Image src={logoWhite} alt="Logo" />
        </Box>
        <Text_24_500_FFFFFF className="tracking-[.02em] leading-[100%] pt-[2.7rem]">
          Got a new password from Admin?
        </Text_24_500_FFFFFF>
        <Text_13_300_FFFFFF className="tracking-[.032em] pt-[.5rem]">
          Please reset your password
        </Text_13_300_FFFFFF>
        <Form.Root className="w-[93.5%] mt-[2.25em]">
          <Form.Field className="grid mb-[.3rem]" name="password">
            <div className="flex items-baseline justify-between">
              <Form.Message
                className="text-[13px] text-white opacity-[0.8]"
                match="valueMissing"
              >
                Please enter your password
              </Form.Message>
            </div>
            <Form.Control asChild>
              <input
                placeholder="Password"
                className="shadow-none box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[1em] appearance-none items-center justify-center text-xs leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6 focus:border-[#FFFFFF] rounded-md mb-[.2rem]"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => handleBlur("password")}
              />
            </Form.Control>
            {isTouched.password && passwordError && (
              <Text_12_400_red className="opacity-[0.8] text-[0.625rem] mb-[.3rem]">
                {passwordError}
              </Text_12_400_red>
            )}
          </Form.Field>
          <Form.Field className="grid mb-[.5rem]" name="rePassword">
            <div className="flex items-baseline justify-between">
              <Form.Message
                className="text-[13px] text-white opacity-[0.8]"
                match="valueMissing"
              >
                Please re-enter your password
              </Form.Message>
            </div>
            <Form.Control asChild>
              <input
                placeholder="Re-Enter Password"
                className="shadow-none box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[1em] appearance-none items-center justify-center text-xs leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6 focus:border-[#FFFFFF] rounded-md mb-[.2rem]"
                type="password"
                required
                value={rePassword}
                onChange={(e) => setRePassword(e.target.value)}
                onBlur={() => handleBlur("rePassword")}
              />
            </Form.Control>
            {isTouched.rePassword && rePasswordError && (
              <Text_12_400_red className="opacity-[0.8] text-[0.625rem] mb-[.3rem]">
                {rePasswordError}
              </Text_12_400_red>
            )}
          </Form.Field>

          <Form.Submit asChild>
            <ButtonInput
              className={`loginButton text-[#FFFFFF] w-full box-border focus:outline-none !border !border-[#FFFFFF] rounded-md ${
                isFormValid ? "cursor-pointer" : ""
              }`}
              onClick={handleSubmitPassword}
              disabled={!isFormValid}
            >
              Update
            </ButtonInput>
          </Form.Submit>
          {error && (
            <Text_12_400_red className="opacity-[0.8] mt-2 text-[0.625rem]">
              {error}
            </Text_12_400_red>
          )}
        </Form.Root>
      </Flex>
    </AuthLayout>
  );
}
