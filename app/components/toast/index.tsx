import React from "react";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import toastIcn from "./../../../public/icons/toast-icon.svg";
import Image from "next/image";

 const Toast = () => (
  <>
    <ToastContainer
      position="top-right"
      autoClose={3000}
      limit={10}
      hideProgressBar={true}
      newestOnTop={true}
      closeOnClick
      rtl={false}
      pauseOnFocusLoss
      draggable
      pauseOnHover
      theme="dark"
    />
  </>
);
export const errorToast = (
  message = "Something went wrong. Try again later!"
) => {
  toast.error(message, {
    icon: ({theme, type}) =>  <Image alt="" height='20' width='20' src={`${toastIcn.src}`}/>, // Custom icon component
  });
  // toast.clearWaitingQueue();
};

export const successToast = (message: string) => {
  toast.success(message, {
    icon: ({theme, type}) =>  <Image alt="" height='20' width='20' src={`${toastIcn.src}`}/>, // Custom icon component
  });
  // toast.clearWaitingQueue();
};
export const infoToast = (message: string) => toast.warning(message, {
  icon: ({theme, type}) =>  <Image alt="" height='20' width='20' src={`${toastIcn.src}`}/>, // Custom icon component
});

export default Toast;