/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import AuthLayout from "../layout";
import { useRouter } from "next/router";
import { useAuthNavigation, useLoader } from "../context/appContext";
import { successToast } from "../components/toast";
import { AppRequest } from "../api/requests";
import LoginPage from "./login";
import ApiKey from "./ApiKey";


interface DataInterface {
  email?: string;
  password?: string;
}

export default function Login() {
  const { activePage, setActivePage, setAuthError } = useAuthNavigation();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [userData, setUserData] = useState<any>();
  const [isBackToLogin, setIsBackToLogin] = useState(false);

  const handleLogin = async (payload: DataInterface) => {
    console.log("click")
  };
  
  return (
    <AuthLayout>
      <div
        className="flex justify-center items-center h-full overflow-hidden"
      >
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
                <ApiKey />
              )}
            </>
          </motion.div>
        </AnimatePresence>
      </div>
    </AuthLayout>
  );
}


