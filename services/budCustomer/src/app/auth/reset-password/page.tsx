"use client";
import React, { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useLoader } from "@/context/authContext";
import { AppRequest } from "@/services/api/requests";
import {
  Text_12_400_red,
  Text_12_400_B3B3B3,
  Text_32_500_FFFFFF,
  Text_14_400_B3B3B3,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/button";
import { successToast, errorToast } from "@/components/toast";

export default function TokenResetPassword() {
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState<string>("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isFormValid, setIsFormValid] = useState(false);
  const [isTokenValid, setIsTokenValid] = useState<boolean | null>(null);
  const [userEmail, setUserEmail] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [isShowNewPassword, setIsShowNewPassword] = useState(false);
  const [isShowConfirmPassword, setIsShowConfirmPassword] = useState(false);
  const [isTouched, setIsTouched] = useState({
    newPassword: false,
    confirmPassword: false,
  });

  useEffect(() => {
    const tokenParam = searchParams.get("token");
    if (tokenParam) {
      setToken(tokenParam);
      validateToken(tokenParam);
    } else {
      setError("No reset token provided. Please check your email link.");
      setIsTokenValid(false);
    }
  }, [searchParams]);

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

      if (response.data.is_valid) {
        setIsTokenValid(true);
        setUserEmail(response.data.email);
        setExpiresAt(response.data.expires_at);
        setError("");
      } else {
        setIsTokenValid(false);
        setError("Invalid or expired reset token. Please request a new password reset.");
      }
    } catch (error: any) {
      console.error("Token validation error:", error);
      setIsTokenValid(false);
      setError(
        error?.response?.data?.message ||
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
      successToast(response.data.message || "Password reset successfully!");

      // Redirect to login after successful password reset
      setTimeout(() => {
        router.push("/login");
      }, 2000);

      hideLoader();
    } catch (error: any) {
      console.error("Password reset error:", error);
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

  const formatExpiryTime = (isoString: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleString();
    } catch {
      return "";
    }
  };

  const handleRequestNewReset = () => {
    router.push("/login");
  };

  // Loading state
  if (isTokenValid === null) {
    return (
      <AuthLayout>
        <div className="flex flex-col justify-center items-center h-full">
          <Text_14_400_B3B3B3>Validating reset token...</Text_14_400_B3B3B3>
        </div>
      </AuthLayout>
    );
  }

  // Invalid token state
  if (isTokenValid === false) {
    return (
      <AuthLayout>
        <div className="flex flex-col justify-center items-center h-full overflow-hidden">
          <div className="w-[70%] h-full open-sans mt-[-1rem] flex justify-center items-center flex-col">
            <div className="mb-8 text-center">
              <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center mb-4">
                Invalid Reset Token
              </Text_32_500_FFFFFF>
              <Text_12_400_B3B3B3 className="text-center mb-4">
                {error || "The reset token is invalid or has expired."}
              </Text_12_400_B3B3B3>
              <Text_12_400_B3B3B3 className="text-center">
                Please request a new password reset from the login page.
              </Text_12_400_B3B3B3>
            </div>

            <PrimaryButton
              onClick={handleRequestNewReset}
              classNames="w-[76.6%]"
            >
              Go to Login
            </PrimaryButton>
          </div>
        </div>
      </AuthLayout>
    );
  }

  // Valid token - show password reset form
  return (
    <AuthLayout>
      <div className="flex flex-col justify-center items-center h-full overflow-hidden">
        <div className="w-[70%] h-full open-sans mt-[-1rem] flex justify-center items-center flex-col">
          <div className="mb-8">
            <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center mb-4">
              Reset Your Password
            </Text_32_500_FFFFFF>
          </div>

          <form
            onSubmit={handleSubmitPassword}
            className="w-[76.6%] mt-[1.6em]"
          >
            <div className="mb-[1.8rem]">
              <div className="flex items-center border border-bud-border rounded-[6px] relative !bg-[transparent]">
                <div className="">
                  <span className="absolute px-1.5 bg-bud-bg-primary top-[-0.4rem] left-1.5 inline-block tracking-[.035rem] z-10 text-xs font-light text-bud-text-muted">
                    New Password
                  </span>
                </div>
                <input
                  type={isShowNewPassword ? "text" : "password"}
                  placeholder="Enter new password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  onBlur={() => handleBlur("newPassword")}
                  autoComplete="new-password"
                  className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-bud-text-primary placeholder:text-bud-text-disabled font-light outline-none !bg-[transparent] border-none rounded-[6px] pt-[.8rem] pb-[.53rem] px-3`}
                />
                <button
                  type="button"
                  onClick={() => setIsShowNewPassword(!isShowNewPassword)}
                  className="text-bud-text-muted cursor-pointer pr-3"
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
              {isTouched.newPassword && newPassword.length > 0 && newPassword.length < 8 && (
                <div className="text-red-500 text-xs mt-1 flex items-center">
                  <img
                    src="/icons/warning.svg"
                    alt="error"
                    className="w-4 h-4 mr-1"
                  />
                  Password must be at least 8 characters long
                </div>
              )}
            </div>

            <div className="mb-[1.8rem]">
              <div className="flex items-center border border-bud-border rounded-[6px] relative !bg-[transparent]">
                <div className="">
                  <span className="absolute px-1.5 bg-bud-bg-primary top-[-0.4rem] left-1.5 inline-block tracking-[.035rem] z-10 text-xs font-light text-bud-text-muted">
                    Confirm Password
                  </span>
                </div>
                <input
                  type={isShowConfirmPassword ? "text" : "password"}
                  placeholder="Re-enter new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  onBlur={() => handleBlur("confirmPassword")}
                  autoComplete="new-password"
                  className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-bud-text-primary placeholder:text-bud-text-disabled font-light outline-none !bg-[transparent] border-none rounded-[6px] pt-[.8rem] pb-[.53rem] px-3`}
                />
                <button
                  type="button"
                  onClick={() => setIsShowConfirmPassword(!isShowConfirmPassword)}
                  className="text-bud-text-muted cursor-pointer pr-3"
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
              {isTouched.confirmPassword && confirmPassword.length > 0 && (
                <>
                  {confirmPassword.length < 8 && (
                    <div className="text-red-500 text-xs mt-1 flex items-center">
                      <img
                        src="/icons/warning.svg"
                        alt="error"
                        className="w-4 h-4 mr-1"
                      />
                      Password must be at least 8 characters long
                    </div>
                  )}
                  {confirmPassword.length >= 8 && newPassword !== confirmPassword && (
                    <div className="text-red-500 text-xs mt-1 flex items-center">
                      <img
                        src="/icons/warning.svg"
                        alt="error"
                        className="w-4 h-4 mr-1"
                      />
                      Passwords do not match
                    </div>
                  )}
                </>
              )}
            </div>

            <PrimaryButton
              type="submit"
              classNames="w-[100%] mt-[1.6rem]"
              disabled={!isFormValid}
            >
              Reset Password
            </PrimaryButton>

            {error && (
              <Text_12_400_red className="opacity-[0.8] mt-2 text-[0.625rem] text-center">
                {error}
              </Text_12_400_red>
            )}
          </form>
        </div>
      </div>
    </AuthLayout>
  );
}
