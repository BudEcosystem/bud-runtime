import { useEffect } from "react";
import { useLoader } from "src/context/appContext";

export function useLoaderOnLoding(loading: boolean) {
  const { showLoader, hideLoader } = useLoader();

  useEffect(() => {
    if (loading) {
      showLoader();
    } else {
      hideLoader();
    }
  }, [loading, showLoader, hideLoader]);
}
