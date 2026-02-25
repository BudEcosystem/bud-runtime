import React from "react";

const isUrl = (str: string) => /^(https?:\/\/|data:)/.test(str);

export const renderToolIcon = (
  icon: string | undefined,
  name: string,
  className: string = "w-5 h-5 object-contain"
): React.ReactNode => {
  if (icon) {
    if (isUrl(icon)) {
      return <img src={icon} alt={name} className={className} />;
    }
    return icon;
  }
  return name.charAt(0).toUpperCase();
};
