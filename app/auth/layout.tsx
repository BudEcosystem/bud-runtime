/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { ReactNode } from "react";
import { Image } from 'antd';

interface LayoutProps {
  children: ReactNode;
}
const AuthLayout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="w-full h-screen logginBg box-border relative">
      <div className="loginWrap w-full h-full loginBg-glass flex justify-between box-border ">
        <div className="loginLeft relative login-left-bg overflow-hidden rounded-[15px] w-[56.4%] m-[.8rem] p-[.8rem]">
          <Image
            alt=""
            src="/images/purple-shadow.png"
            className="absolute bottom-[-28em] left-[-29em] rotate-[14deg] opacity-[.3]"
          />
          <div
            className="flex flex-col justify-between w-[100%] 2xl:max-w-[500px] 1680px:max-w-[650px] h-full px-[3.5rem] pt-[3rem] pb-[2.9rem]"
          >
            <Image alt="" src="/images/BudLogo.png" preview={false} className="w-[6.6em] h-auto" />
            <div className="logo-text text-[2.25em] 2xl:text-[2.5rem] 1680px:text-[2.4rem] text-white open-sans tracking-[.0rem] leading-[3.1rem] w-[400px] 1680px:w-[500px] 2560px:w-[700px]">
              Useful. Private. Real time. Offline. Safe Intelligence in your
              Pocket.
            </div>
          </div>
        </div>
        <div className="loginRight  w-[43.6%] h-full">{children}</div>
      </div>
    </div>
  );
};
export default AuthLayout;
