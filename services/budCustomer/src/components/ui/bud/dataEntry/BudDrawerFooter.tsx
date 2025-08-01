import { useContext } from "react";
import FormProgress from "../progress/FormProgress";
import { BudFormContext } from "../context/BudFormContext";

export interface BudProps {
  children: React.ReactNode;
}

export function BudDrawerFooter(props: BudProps) {
  const { form, isExpandedView } = useContext(BudFormContext);
  return <div className="drawerFooter z-[5000] min-[4.1875rem] flex flex-col	justify-start">
    {isExpandedView ? null : <FormProgress />}
    <div style={{ justifyContent: "space-between" }} className={`h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]`}>
      {props.children}
    </div>
  </div>;
}
