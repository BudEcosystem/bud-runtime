import { useEffect } from "react";
import { useRouter } from "next/router";

const useAuth = (WrappedComponent) => {
  const AuthComponent = (props) => {
    const router = useRouter();
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;

    useEffect(() => {
      if (!token) {
        router.push("/login");
      }
    }, [token, router]); // Add 'router' as a dependency

    if (!token) {
      return null; // Return null or a loading spinner while redirecting
    }

    return <WrappedComponent {...props} />;
  };

  // Set a display name for the component for debugging purposes
  AuthComponent.displayName = `useAuth(${WrappedComponent.displayName || WrappedComponent.name || "Component"})`;

  return AuthComponent;
};

export default useAuth;
