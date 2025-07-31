import { useDrawer } from "@/hooks/useDrawer";
import { BudFormContext } from "../context/BudFormContext";
import { useContext } from "react";
import { useDeployModel } from "@/stores/useDeployModel";
import { usePerfomanceBenchmark } from "@/stores/usePerfomanceBenchmark";

export interface BudProps {
  children: React.ReactNode;
  classNames?: any,
  center?: boolean,
}

export function BudWraperBox(props: BudProps) {
  const { step, cancelAlert, setCancelAlert, closeDrawer, closeExpandedStep, expandedStep } = useDrawer();
  const { form, isExpandedView } = useContext(BudFormContext);
  const { loading } = useDeployModel();
  const { loading: performanceLoading } = usePerfomanceBenchmark();

  // Blur logic
  return (
    <>
      <div className={`BudWraperBox scrollBox py-[20px] overflow-y-auto h-full  ${expandedStep && !isExpandedView ? 'blur-removethistoaddblur-[.25rem]' : ''}  ${(loading || performanceLoading) ? 'blur': ''} ${props.classNames} ${props.center && 'flex flex-col	justify-center mt-[0]'}`}>
        {props.children}
      </div>
    </>
  );
}