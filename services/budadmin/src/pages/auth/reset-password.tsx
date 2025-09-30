"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Image from "next/image";
import { Box, Flex, Text } from "@radix-ui/themes";
import AuthLayout from "./layout";
import { useLoader } from "../../context/appContext";
import { AppRequest } from "../api/requests";
import {
  Text_12_400_red,
  Text_12_400_B3B3B3,
  Text_32_500_FFFFFF,
  Text_14_400_B3B3B3,
  Text_24_500_FFFFFF,
  Text_13_300_FFFFFF,
} from "../../components/ui/text";
import { ButtonInput } from "../../components/ui/button";
import { successToast, errorToast } from "../../components/toast";
import logoWhite from "../../../public/images/logoBud.png";
import * as Form from "@radix-ui/react-form";

function TokenResetPasswordContent() {
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [token, setToken] = useState<string>("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isFormValid, setIsFormValid] = useState(false);
  const [isTokenValid, setIsTokenValid] = useState<boolean | null>(null);
  const [isShowNewPassword, setIsShowNewPassword] = useState(false);
  const [isShowConfirmPassword, setIsShowConfirmPassword] = useState(false);
  const [isTouched, setIsTouched] = useState({
    newPassword: false,
    confirmPassword: false,
  });

  useEffect(() => {
    if (!router.isReady) return;

    const tokenParam = router.query.token as string;

    if (tokenParam) {
      setToken(tokenParam);
      validateToken(tokenParam);
    } else {
      setError("No reset token provided. Please check your email link.");
      setIsTokenValid(false);
    }
  }, [router.isReady, router.query.token]);

  useEffect(() => {
    const validateForm = () => {
      const newPasswordValid = newPassword.length >= 8;
      const confirmPasswordValid = confirmPassword.length >= 8;
      const passwordsMatch = newPassword === confirmPassword;

      setIsFormValid(
        newPasswordValid &&
        confirmPasswordValid &&
        passwordsMatch &&
        isTokenValid === true
      );
    };
    validateForm();
  }, [newPassword, confirmPassword, isTokenValid]);

  const validateToken = async (token: string) => {
    showLoader();
    try {
      const response = await AppRequest.Post("/users/validate-reset-token", {
        token: token,
      });

      // Check both response and response.data for the validation result
      const validationData = response?.data || response;
      const isValid = validationData?.is_valid || validationData?.result?.is_valid;

      if (isValid) {
        setIsTokenValid(true);
        setError("");
      } else {
        setIsTokenValid(false);
        setError("Invalid or expired reset token. Please request a new password reset.");
      }
    } catch (error: any) {
      setIsTokenValid(false);
      setError(
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        "Failed to validate reset token. Please try again."
      );
    } finally {
      hideLoader();
    }
  };

  const handleSubmitPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!token || !isTokenValid) {
      setError("Invalid reset token. Please request a new password reset.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    showLoader();
    setError("");

    const payload = {
      token: token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    };

    try {
      const response = await AppRequest.Post("/users/reset-password-with-token", payload);

      const responseData = response?.data || response;
      const message = responseData?.message || responseData?.result?.message || "Password reset successfully!";

      successToast(message);

      // Redirect to login after successful password reset
      setTimeout(() => {
        router.push("/auth/logIn");
      }, 2000);

      hideLoader();
    } catch (error: any) {
      setError(
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        "Failed to reset password. Please try again."
      );
      hideLoader();
    }
  };

  const handleBlur = (field: string) => {
    setIsTouched({ ...isTouched, [field]: true });
  };

  const handleRequestNewReset = () => {
    router.push("/auth/logIn");
  };

  // Loading state
  if (isTokenValid === null) {
    return (
      <AuthLayout>
        <Flex
          className="w-full h-full bg-[#0f0f0f] border border-[#18191B] rounded-2xl overflow-hidden"
          direction="column"
          justify="center"
          align="center"
        >
          <Text_14_400_B3B3B3>Validating reset token...</Text_14_400_B3B3B3>
        </Flex>
      </AuthLayout>
    );
  }

  // Invalid token state
  if (isTokenValid === false) {
    return (
      <AuthLayout>
        <Flex
          className="w-full h-full bg-[#0f0f0f] border border-[#18191B] rounded-2xl overflow-hidden px-[23.4%]"
          direction="column"
          justify="center"
        >
          <Box className="w-[5.2em] mb-8">
            <Image src={logoWhite} alt="Logo" />
          </Box>
          <Text_24_500_FFFFFF className="tracking-[.02em] leading-[100%] mb-4">
            Invalid Reset Token
          </Text_24_500_FFFFFF>
          <Text_12_400_B3B3B3 className="mb-4">
            {error || "The reset token is invalid or has expired."}
          </Text_12_400_B3B3B3>
          <Text_12_400_B3B3B3 className="mb-8">
            Please request a new password reset from the login page.
          </Text_12_400_B3B3B3>

          <ButtonInput
            onClick={handleRequestNewReset}
            className="loginButton text-[#FFFFFF] w-full box-border focus:outline-none !border !border-[#FFFFFF] rounded-md cursor-pointer"
          >
            Go to Login
          </ButtonInput>
        </Flex>
      </AuthLayout>
    );
  }

  // Valid token - show password reset form
  return (
    <AuthLayout>
      <Flex
        className="w-full h-full bg-[#0f0f0f] border border-[#18191B] rounded-2xl overflow-hidden px-[23.4%]"
        direction="column"
        justify="center"
      >
        <Box className="w-[5.2em] mb-8">
          <Image src={logoWhite} alt="Logo" />
        </Box>
        <Text_24_500_FFFFFF className="tracking-[.02em] leading-[100%] mb-2">
          Reset Your Password
        </Text_24_500_FFFFFF>
        <Text_13_300_FFFFFF className="tracking-[.032em] mb-8">
          Enter your new password below
        </Text_13_300_FFFFFF>

        <Form.Root className="w-[93.5%]" onSubmit={handleSubmitPassword}>
          <Form.Field className="grid mb-6" name="newPassword">
            <div className="relative">
              <Form.Label className="text-xs font-light text-white/70 absolute -top-2 left-3 bg-[#0f0f0f] px-1">
                New Password
              </Form.Label>
              <div className="flex items-center">
                <Form.Control asChild>
                  <input
                    type={isShowNewPassword ? "text" : "password"}
                    placeholder="Enter new password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    onBlur={() => handleBlur("newPassword")}
                    autoComplete="new-password"
                    className="shadow-none box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[2.5em] appearance-none items-center justify-center text-xs leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6 focus:border-[#FFFFFF] rounded-md pr-10"
                    required
                  />
                </Form.Control>
                <button
                  type="button"
                  onClick={() => setIsShowNewPassword(!isShowNewPassword)}
                  className="text-white/50 cursor-pointer -ml-8 z-10"
                >
                  {isShowNewPassword ? (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path
                        d="M2 10C3.5 6.5 7 4 10 4C13 4 16.5 6.5 18 10C16.5 13.5 13 16 10 16C7 16 3.5 13.5 2 10Z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path
                        d="M2 10C3.5 6.5 7 4 10 4C13 4 16.5 6.5 18 10C16.5 13.5 13 16 10 16C7 16 3.5 13.5 2 10Z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <line
                        x1="4"
                        y1="16"
                        x2="16"
                        y2="4"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            {isTouched.newPassword && newPassword.length > 0 && newPassword.length < 8 && (
              <Text_12_400_red className="opacity-[0.8] text-[0.625rem] mt-1">
                Password must be at least 8 characters long
              </Text_12_400_red>
            )}
          </Form.Field>

          <Form.Field className="grid mb-6" name="confirmPassword">
            <div className="relative">
              <Form.Label className="text-xs font-light text-white/70 absolute -top-2 left-3 bg-[#0f0f0f] px-1">
                Confirm Password
              </Form.Label>
              <div className="flex items-center">
                <Form.Control asChild>
                  <input
                    type={isShowConfirmPassword ? "text" : "password"}
                    placeholder="Re-enter new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    onBlur={() => handleBlur("confirmPassword")}
                    autoComplete="new-password"
                    className="shadow-none box-border w-full specialInput bg-blackA2 shadow-blackA6 inline-flex h-[2.5em] appearance-none items-center justify-center text-xs leading-none text-white shadow-[0_0_0_1px] outline-none hover:shadow-[0_0_0_1px_black] focus:shadow-[0_0_0_2px_black] selection:color-white selection:bg-blackA6 focus:border-[#FFFFFF] rounded-md pr-10"
                    required
                  />
                </Form.Control>
                <button
                  type="button"
                  onClick={() => setIsShowConfirmPassword(!isShowConfirmPassword)}
                  className="text-white/50 cursor-pointer -ml-8 z-10"
                >
                  {isShowConfirmPassword ? (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path
                        d="M2 10C3.5 6.5 7 4 10 4C13 4 16.5 6.5 18 10C16.5 13.5 13 16 10 16C7 16 3.5 13.5 2 10Z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path
                        d="M2 10C3.5 6.5 7 4 10 4C13 4 16.5 6.5 18 10C16.5 13.5 13 16 10 16C7 16 3.5 13.5 2 10Z"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        fill="none"
                      />
                      <line
                        x1="4"
                        y1="16"
                        x2="16"
                        y2="4"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            {isTouched.confirmPassword && confirmPassword.length > 0 && (
              <>
                {confirmPassword.length < 8 && (
                  <Text_12_400_red className="opacity-[0.8] text-[0.625rem] mt-1">
                    Password must be at least 8 characters long
                  </Text_12_400_red>
                )}
                {confirmPassword.length >= 8 && newPassword !== confirmPassword && (
                  <Text_12_400_red className="opacity-[0.8] text-[0.625rem] mt-1">
                    Passwords do not match
                  </Text_12_400_red>
                )}
              </>
            )}
          </Form.Field>

          <Form.Submit asChild>
            <ButtonInput
              type="submit"
              className={`loginButton text-[#FFFFFF] w-full box-border focus:outline-none !border !border-[#FFFFFF] rounded-md ${
                isFormValid ? "cursor-pointer" : ""
              }`}
              disabled={!isFormValid}
              onClick={handleSubmitPassword}
            >
              Reset Password
            </ButtonInput>
          </Form.Submit>

          {error && (
            <Text_12_400_red className="opacity-[0.8] mt-2 text-[0.625rem] text-center">
              {error}
            </Text_12_400_red>
          )}
        </Form.Root>
      </Flex>
    </AuthLayout>
  );
}

export default function TokenResetPassword() {
  return <TokenResetPasswordContent />;
}
