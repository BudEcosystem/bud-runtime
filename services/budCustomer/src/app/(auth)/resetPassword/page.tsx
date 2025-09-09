"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthLayout from "@/components/auth/AuthLayout";
import { useLoader } from "@/context/authContext";
import { AppRequest } from "@/services/api/requests";
import {
  Text_12_400_red,
  Text_12_400_B3B3B3,
  Text_32_500_FFFFFF,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/button";
import { successToast } from "@/components/toast";

export default function ResetPassword() {
  const { showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [userId, setUserId] = useState<string>("");
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
  const [isShowPassword, setIsShowPassword] = useState(false);
  const [isShowRePassword, setIsShowRePassword] = useState(false);

  useEffect(() => {
    const validateForm = () => {
      const rePasswordValid = rePassword.length >= 8;
      const passwordValid = password.length >= 8;
      const passwordsMatch = password === rePassword;

      setRePasswordError(
        rePasswordValid ? "" : "Password must be at least 8 characters long",
      );
      setPasswordError(
        passwordValid ? "" : "Password must be at least 8 characters long",
      );
      setError(
        rePassword.length > 0 && !passwordsMatch
          ? "Passwords do not match"
          : "",
      );
      setIsFormValid(rePasswordValid && passwordValid && passwordsMatch);
    };
    validateForm();
  }, [rePassword, password]);

  const handleSubmitPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!userId) {
      setError("User ID not found. Please try again.");
      return;
    }

    showLoader();
    setError("");

    const payload = {
      password: password,
    };

    try {
      const response = await AppRequest.Patch(`/users/${userId}`, payload);
      successToast(response.data.message || "Password reset successfully");
      router.push("/login");
      localStorage.clear();
      hideLoader();
    } catch (error: any) {
      console.error("Password reset error:", error);
      setError(
        error?.response?.data?.detail ||
          error?.response?.data?.message ||
          "Something went wrong",
      );
      hideLoader();
    }
  };

  const handleBlur = (field: string) => {
    setIsTouched({ ...isTouched, [field]: true });
  };

  useEffect(() => {
    // Fetch user data on component mount
    const fetchUserData = async () => {
      try {
        const response = await AppRequest.Get("/users/me");
        if (response.data?.user?.id) {
          setUserId(response.data.user.id);
        } else if (response.data?.id) {
          setUserId(response.data.id);
        }
      } catch (error) {
        console.error("Failed to fetch user data:", error);
        setError("Failed to fetch user information. Please try again.");
      }
    };

    fetchUserData();
  }, []);

  return (
    <AuthLayout>
      <div className="flex flex-col justify-center items-center h-full overflow-hidden">
        <div className="w-[70%] h-full open-sans mt-[-1rem] flex justify-center items-center flex-col">
          <div className="mb-8">
            <Text_32_500_FFFFFF className="tracking-[.01em] leading-[100%] text-center mb-4">
              Reset Your Password
            </Text_32_500_FFFFFF>
            <Text_12_400_B3B3B3 className="text-center">
              Got a new password from Admin? Please reset your password
            </Text_12_400_B3B3B3>
          </div>

          <form
            onSubmit={handleSubmitPassword}
            className="w-[76.6%] mt-[1.6em]"
          >
            <div className="mb-[1.8rem]">
              <div className="flex items-center border border-bud-border rounded-[6px] relative !bg-[transparent]">
                <div className="">
                  <span className="absolute px-1.5 bg-bud-bg-primary top-[-0.4rem] left-1.5 inline-block tracking-[.035rem] z-10 text-xs font-light text-bud-text-muted">
                    Password
                  </span>
                </div>
                <input
                  type={isShowPassword ? "text" : "password"}
                  placeholder="Enter new password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => handleBlur("password")}
                  autoComplete="new-password"
                  className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-bud-text-primary placeholder:text-bud-text-disabled font-light outline-none !bg-[transparent] border-none rounded-[6px] pt-[.8rem] pb-[.53rem] px-3`}
                />
                <button
                  type="button"
                  onClick={() => setIsShowPassword(!isShowPassword)}
                  className="text-bud-text-muted cursor-pointer pr-3"
                >
                  {isShowPassword ? (
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
              {isTouched.password && passwordError && (
                <div className="text-red-500 text-xs mt-1 flex items-center">
                  <img
                    src="/icons/warning.svg"
                    alt="error"
                    className="w-4 h-4 mr-1"
                  />
                  {passwordError}
                </div>
              )}
            </div>

            <div className="mb-[1.8rem]">
              <div className="flex items-center border border-bud-border rounded-[6px] relative !bg-[transparent]">
                <div className="">
                  <span className="absolute px-1.5 bg-bud-bg-primary top-[-0.4rem] left-1.5 inline-block tracking-[.035rem] z-10 text-xs font-light text-bud-text-muted">
                    Re-Enter Password
                  </span>
                </div>
                <input
                  type={isShowRePassword ? "text" : "password"}
                  placeholder="Re-enter new password"
                  value={rePassword}
                  onChange={(e) => setRePassword(e.target.value)}
                  onBlur={() => handleBlur("rePassword")}
                  autoComplete="new-password"
                  className={`h-auto leading-[100%] w-full placeholder:text-xs text-xs text-bud-text-primary placeholder:text-bud-text-disabled font-light outline-none !bg-[transparent] border-none rounded-[6px] pt-[.8rem] pb-[.53rem] px-3`}
                />
                <button
                  type="button"
                  onClick={() => setIsShowRePassword(!isShowRePassword)}
                  className="text-bud-text-muted cursor-pointer pr-3"
                >
                  {isShowRePassword ? (
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
              {isTouched.rePassword && rePasswordError && (
                <div className="text-red-500 text-xs mt-1 flex items-center">
                  <img
                    src="/icons/warning.svg"
                    alt="error"
                    className="w-4 h-4 mr-1"
                  />
                  {rePasswordError}
                </div>
              )}
            </div>

            <PrimaryButton
              type="submit"
              classNames="w-[100%] mt-[1.6rem]"
              disabled={!isFormValid}
            >
              Update Password
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
