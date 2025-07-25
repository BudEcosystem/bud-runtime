"use client";

import React, {
    createContext,
    useCallback,
    useContext,
    useState,
  } from "react";
import { Image } from "antd";

interface LoaderContextType {
    isLoading: boolean;
    showLoader: () => void;
    hideLoader: () => void;
  }

const LoaderContext = createContext<LoaderContextType | undefined>(undefined);


export const LoaderProvider: React.FC<{ children: React.ReactNode }> = ({
    children,
  }) => {
    const [isLoading, setIsLoading] = useState(true);
  
    const showLoader = useCallback(() => setIsLoading(true), []);
    const hideLoader = useCallback(() => setIsLoading(false), []);
  
    return (
      <LoaderContext.Provider value={{ isLoading, showLoader, hideLoader }}>
        {children}
      </LoaderContext.Provider>
    );
  };

  export const useLoader = () => {
    const context = useContext(LoaderContext);
    if (!context) {
      throw new Error("useLoader must be used within a LoaderProvider");
    }
    return context;
  };


  export const LoaderWrapper = () => {
    const { isLoading } = useLoader();
  
    return isLoading ? (
      <div className="z-[1000] fixed top-0 left-0 w-screen h-screen flex justify-center items-center	backdrop-blur-[2px]">
        {/* <Spinner size="3" className="z-[1000] relative w-[20px] h-[20px] block" /> */}
        <Image
          width={80}
          preview={false}
          className="w-[80px] h-[80px]"
          src={'/loading-bud.gif'}
          alt="Logo"
        />
      </div>
    ) : null;
  };