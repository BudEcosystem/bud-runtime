import React from "react";
import "react-toastify/dist/ReactToastify.css";
import { ToastContainer, ToastContentProps, toast } from "react-toastify";
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

export const successToast = (message: string | number | bigint | boolean | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | React.ReactPortal | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | null | undefined> | ((props: ToastContentProps<unknown>) => React.ReactNode) | null | undefined) => {
  toast.success(message, {
    icon: ({theme, type}) =>  <Image alt="" height='20' width='20' src={`${toastIcn.src}`}/>, // Custom icon component
  });
  // toast.clearWaitingQueue();
};
export const infoToast = (message: string | number | bigint | boolean | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | React.ReactPortal | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | null | undefined> | ((props: ToastContentProps<unknown>) => React.ReactNode) | null | undefined) => toast.warning(message, {
  icon: ({theme, type}) =>  <Image alt="" height='20' width='20' src={`${toastIcn.src}`}/>, // Custom icon component
});

export default Toast;