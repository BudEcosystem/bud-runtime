import React, { useState } from "react";

interface FloatLabelProps {
  children: React.ReactNode;
  label: React.ReactNode;
  value?: any;
  classNames?: string;
}

const FloatLabel = (props: FloatLabelProps) => {
  const [focus, setFocus] = useState(false);
  const { children, label, value, classNames } = props;

  const labelClass = focus || value ? "label label-float" : "label";

  return (
    <div
      className={`float-label`}
      onBlur={() => setFocus(false)}
      onFocus={() => setFocus(true)}
    >
      {children}
      <label className={`text-nowrap ${labelClass} ${classNames}`}>{label}</label>
    </div>
  );
};

export default FloatLabel;
