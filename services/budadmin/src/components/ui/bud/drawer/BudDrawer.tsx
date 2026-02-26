import React, { useEffect } from "react";
import { Drawer } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "../context/BudFormContext";
import { useForm } from "src/hooks/useForm";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { BudForm } from "../dataEntry/BudForm";
import { useAddAgent } from "@/stores/useAddAgent";
import flows from "src/hooks/drawerFlows";

const BudDrawer: React.FC = () => {
  const {
    step,
    expandedStep,
    isDrawerOpen,
    setCancelAlert,
    closeDrawer,
    isFailed,
    drawerProps,
    currentFlow,
  } = useDrawer();
  const { form, submittable, loading, setLoading, values } = useForm({
    initialData: {},
  });

  // Get formResetKey from useAddAgent store to force remount of add-agent flow components
  const { formResetKey } = useAddAgent();

  if (!step) {
    return null;
  }

  const screenWidth = window.innerWidth;
  const isFullPage = !!(currentFlow && flows[currentFlow]?.fullPage);

  let width = 400;

  if (isFullPage) {
    width = screenWidth;
  } else if (screenWidth > 2560) {
    width = screenWidth * 0.35;
  } else if (screenWidth > 1920) {
    width = screenWidth * 0.4322;
  } else if (screenWidth > 1280) {
    width = screenWidth * 0.433;
  } else if (screenWidth > 1024) {
    width = 450;
  }

  const isExpanded = Boolean(expandedStep);
  const drawerWidth = isFullPage ? screenWidth : (isExpanded ? width * 2 : width);

  return (
    <Drawer
      id="bud-drawer"
      className="drawerRoot bg-transparent flex  flex-col shadow-none w-full border relative visible-drawer pr-[.6rem]"
      closeIcon={null}
      classNames={{
        wrapper: isFullPage
          ? "shadow-none"
          : "bg-transparent my-[.75rem] mr-[0.6875rem]rounded-[17px] shadow-none",
        mask: isFullPage
          ? "bud-drawer-mask"
          : "bg-transparent bud-drawer-mask",
        body: "flex flex-row bg-transparent",
      }}
      styles={{
        wrapper: {
          width: drawerWidth,
        },
      }}
      open={isDrawerOpen}
      onClose={() => {
        if (step.confirmClose) {
          setCancelAlert(true);
        } else {
          closeDrawer();
        }
      }}
      closable={false}
    >
      {step?.component && (
        <div
          className="drawerBackground"
          style={{
            width: isFullPage ? "100%" : width,
            // paddingRight: ".7rem",
            height: "100%",
          }}
        >
          <BudFormContext.Provider
            value={{
              form,
              submittable,
              loading,
              setLoading,
              values,
              isExpandedView: false,
              isExpandedViewOpen: Boolean(expandedStep),
            }}
          >
            <step.component
              key={currentFlow === 'add-agent' ? `${step.id}-${formResetKey}` : step.id}
              {...step?.properties}
              {...drawerProps}
            />
          </BudFormContext.Provider>
        </div>
      )}
      {expandedStep?.component && (
        <>
          <div
            className="border-gradient border-gradient-purple drawerBackground"
            style={{
              width,
              height: "100%",
            }}
          >
            <BudFormContext.Provider
              value={{
                form,
                submittable,
                loading,
                setLoading,
                values,
                isExpandedView: true,
                isExpandedViewOpen: true,
              }}
            >
              <expandedStep.component {...step?.properties} />
            </BudFormContext.Provider>
          </div>
        </>
      )}
      {!step?.component && !expandedStep?.component && (
        <div
          className="border-gradient border-gradient-purple drawerBackground"
          style={{
            width,
            height: "100%",
          }}
        >
          <BudFormContext.Provider
            value={{
              form,
              submittable,
              loading,
              setLoading,
              values,
              isExpandedView: true,
              isExpandedViewOpen: true,
            }}
          >
            <BudForm data={{}}>
              <BudStepAlert
                description={`The step you are trying to access is not available. ${step?.id}`}
                title="Error"
              />
            </BudForm>
          </BudFormContext.Provider>
        </div>
      )}
    </Drawer>
  );
};

export default BudDrawer;
