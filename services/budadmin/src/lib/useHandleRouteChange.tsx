import { useRouter } from "next/router";
import { useEffect } from "react";

const useHandleRouteChange = (callback: () => void) => {
  const router = useRouter();

  useEffect(() => {
    const handleRouteChange = (url: string) => {
      callback();
    };

    router.events.on("routeChangeStart", handleRouteChange);

    return () => {
      router.events.off("routeChangeStart", handleRouteChange);
    };
  }, [router, callback]);
};

export default useHandleRouteChange;
