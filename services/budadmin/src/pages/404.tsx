import { useRouter } from "next/router";
import React, { useEffect } from "react";

/**
 * Redirect to home page
 */
function NotFound() {
  const router = useRouter();
  useEffect(() => {
    router.push("/");
  }, []);
}

export default NotFound;
