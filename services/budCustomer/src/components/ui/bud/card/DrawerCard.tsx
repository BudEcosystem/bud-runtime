import React from "react";

interface DrawerCardProps {
  children?: React.ReactNode;
  classNames?: any
}

function DrawerCard({ children, classNames }: DrawerCardProps) {
  return (
    <div className={`px-[1.4rem] py-[.9rem] rounded-es-lg rounded-ee-lg pb-4 ${classNames}`}>
      {children}
    </div>
  );
}

export default DrawerCard;
