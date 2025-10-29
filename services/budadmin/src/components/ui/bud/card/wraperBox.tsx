import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "../context/BudFormContext";
import { useContext } from "react";
import { useDeployModel } from "src/stores/useDeployModel";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

export interface BudProps {
  children: React.ReactNode;
  classNames?: any;
  center?: boolean;
  onScroll?: (e: React.UIEvent<HTMLDivElement>) => void;
}

export function BudWraperBox(props: BudProps) {
  const {
    step,
    cancelAlert,
    setCancelAlert,
    closeDrawer,
    closeExpandedStep,
    expandedStep,
  } = useDrawer();
  const { form, isExpandedView } = useContext(BudFormContext);
  const { loading } = useDeployModel();
  const { loading: performanceLoading } = usePerfomanceBenchmark();

  // Blur logic
  return (
    <>
      <div
        className={`BudWraperBox scrollBox py-[20px] overflow-y-auto h-full  ${expandedStep && !isExpandedView ? "blur-removethistoaddblur-[.25rem]" : ""}  ${loading || performanceLoading ? "blur" : ""} ${props.classNames} ${props.center && "flex flex-col	justify-center mt-[0]"}`}
        onScroll={props.onScroll}
      >
        {props.children}
      </div>
    </>
  );
}
