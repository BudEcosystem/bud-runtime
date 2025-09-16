import React from "react";
import AuthLayout from "./layout";
import { useRouter } from "next/router";
import Login from "./logIn";
import SignIn from "./register";

const AuthPage = () => {
  const router = useRouter();
  const renderDashboardContent = () => {
    switch (router.pathname) {
      case "/Login":
        return <Login />;
      case "/signIn":
        return <SignIn />;
      default:
        return null;
    }
  };
  return <AuthLayout>{renderDashboardContent()}</AuthLayout>;
};

export default AuthPage;
