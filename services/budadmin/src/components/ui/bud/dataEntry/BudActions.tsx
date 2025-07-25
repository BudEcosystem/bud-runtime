import React from "react";

type BudDrawerActionsProps = {
  children?: React.ReactNode;
};

function BudDrawerActions({ children }: BudDrawerActionsProps) {
  return (
    <div
      style={{ justifyContent: "space-between" }}
      className={`h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]`}
    >
      {children}
    </div>
  );
}

export default BudDrawerActions;
