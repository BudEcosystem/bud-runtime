import { use, useEffect, useState } from "react";

export function useShortCut({ key, action }) {
  const [metaKeyPressed, setMetaKeyPressed] = useState(false);

  const handleKeyDown = (e) => {
    if (e.target !== document.body) {
      return;
    }
    const isMetaKey = e.metaKey;
    setMetaKeyPressed(isMetaKey);

    if (isMetaKey && e.key === key) {
      e.preventDefault();
      action();
    }
  };

  const handleKeyUp = (e) => {
    setMetaKeyPressed(false);
    if (e.metaKey && e.key === key) {
      e.preventDefault();
    }
  };

  const handleBlur = () => {
    setMetaKeyPressed(false);
  };

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  useEffect(() => {
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", handleBlur);
    return () => {
      window.removeEventListener("keyup", handleKeyDown);
      window.removeEventListener("blur", () => {
        setMetaKeyPressed(false);
      });
    };
  }, []);

  return {
    metaKeyPressed,
  };
}
