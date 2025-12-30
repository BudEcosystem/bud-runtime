/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useEffect, useState } from "react";
import { Flex } from "@radix-ui/themes";
import { useRouter } from "next/router";
import { AppRequest } from "./../../api/requests";
import AuthLayout from "../layout";
import { useAuthNavigation, useLoader } from "./../../../context/appContext";
import LoginPage from "@/components/auth/login";
import ResetPasswordPage from "@/components/auth/resetPassword";
import HuggingfaceKeyPage from "@/components/auth/huggingface";
import ContactAdmin from "@/components/auth/contactAdmin";
import RequestSent from "@/components/auth/requestSent";
import { successToast } from "@/components/toast";
import { motion, AnimatePresence } from "framer-motion";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import { useUser } from "src/stores/useUser";

interface DataInterface {
  email?: string;
  password?: string;
  user_type?: string;
  remember_me?: boolean;
}

export default function Login() {
  const { user } = useUser();
  const { activePage, setActivePage, setAuthError, authError } =
    useAuthNavigation();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [userData, setUserData] = useState<any>();
  const [isBackToLogin, setIsBackToLogin] = useState(false);
  useEffect(() => {
    if (activePage === 4) {
      setTimeout(() => {
        setIsBackToLogin(true);
      }, 500);
    } else {
      setTimeout(() => {
        setIsBackToLogin(false);
      }, 500);
    }
  }, [activePage]);

  const getUser = async () => {
    try {
      const response: any = await AppRequest.Get(`/users/me`);
      localStorage.setItem("User", JSON.stringify(response.data.result));
      let getData: any = response.data.result;
      setUserId(getData.id);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  };
  const handleLogin = async (payload: DataInterface) => {
    showLoader();
    console.log("payload", payload);
    try {
      const loginPayload: any = {
        email: payload.email,
        password: payload.password,
        user_type: "admin",
        remember_me: payload.remember_me,
      };
      const response: any = await AppRequest.Post("auth/login", loginPayload);
      const data = response.data;
      if (data.success) {
        successToast(data.message);
        setAuthError("");
      }

      setUserData(data.token);
      localStorage.setItem("access_token", data.token.access_token);
      localStorage.setItem("refresh_token", data.token.refresh_token);

      if (data.is_reset_password || data.first_login) {
        setActivePage(2);
        getUser();
        hideLoader();
      } else {
        router.push("/dashboard");
        // setActivePage(2);
        hideLoader();
      }
    } catch (error) {
      console.error("Login error:", error);
      console.error(typeof error);
      if (typeof error.message === "string") {
        setAuthError(error.message);
      }
      hideLoader();
    }
  };

  const handleResetPassword = async (payload: string) => {
    showLoader();
    try {
      const response = await AppRequest.Patch(`users/${user?.id}`, {
        password: payload,
      });
      if (userData?.first_login) {
        setActivePage(3);
      } else {
        router.push("/dashboard");
      }
      successToast(response.data.message);
      hideLoader();
    } catch (error) {
      console.error("Login error:", error);
      hideLoader();
    }
  };

  const handleAddHuggingFaceKey = async (key: string) => {
    showLoader();
    try {
      const payload = {
        type: "huggingface",
        key,
      };
      const response: any = await AppRequest.Post("/credentials/", payload);
      hideLoader();
      const data = response.data;
      if (data.success) {
        successToast(data.message);
        validateUser();
      }
    } catch (error) {
      hideLoader();
    }
  };

  const validateUser = async () => {
    showLoader();
    try {
      const response: any = await AppRequest.Patch("/users/onboard");
      hideLoader();
      const data = response.data;
      if (data.success) {
        successToast(data.message);
        router.push("/dashboard");
      }
    } catch (error) {
      hideLoader();
    }
  };
  const handleForgetPassword = async (email: string) => {
    showLoader();
    try {
      const response = await AppRequest.Post(`users/reset-password`, {
        email,
      });
      if (response) {
        setActivePage(1);
      }
      console.log("response", response);
      successToast(response.data.message);
      hideLoader();
    } catch (error) {
      console.error("Reset password error:", error);
      hideLoader();
    }
  };
  return (
    <AuthLayout>
      <div className="flex flex-col justify-center items-center  h-full overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activePage}
            initial={{ x: isBackToLogin ? -70 : 70, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: isBackToLogin ? 70 : -70, opacity: 0 }}
            transition={{ duration: 0.4, ease: "linear" }}
            className="w-[70%] h-full open-sans mt-[-1rem] flex justify-center items-center flex-col"
          >
            <>{activePage === 1 && <LoginPage onSubmit={handleLogin} />}</>
            <>
              {activePage === 2 && (
                <ResetPasswordPage onSubmit={handleResetPassword} />
              )}
              {activePage === 3 && (
                <HuggingfaceKeyPage onSubmit={handleAddHuggingFaceKey} />
              )}
              {activePage === 4 && (
                <ContactAdmin onSubmit={handleForgetPassword} />
              )}
              {activePage === 5 && <RequestSent />}
            </>
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}
