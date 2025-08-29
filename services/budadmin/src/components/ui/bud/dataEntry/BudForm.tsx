import { Form, Image, Spin, Tooltip } from "antd";
import { BudFormContext } from "../context/BudFormContext";
import { useForm } from "src/hooks/useForm";
import DrawerBreadCrumbNavigation from "../card/DrawerBreadCrumbNavigation";
import { useDrawer } from "src/hooks/useDrawer";
import { useContext, useEffect } from "react";
import { BudDrawerFooter } from "./BudDrawerFooter";
import { PrimaryButton, SecondaryButton } from "../form/Buttons";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { BudDrawerLayout } from "./BudDrawerLayout";
import { BudWraperBox } from "../card/wraperBox";
import { useWorkflow } from "src/stores/useWorkflow";
import { useDeployModel } from "src/stores/useDeployModel";
import loaderIcn from "public/icons/loader.gif";
import { Text_12_400_5B6168 } from "../../text";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";


interface FooterProps {
  backText?: React.ReactNode;
  nextText?: React.ReactNode;
  onBack?: () => void;
  onNext?: (values: any) => void;
  disableNext?: boolean;
  disableBack?: boolean;
  showBack?: boolean;
}

function Footer(props: FooterProps) {
  const { form } = useContext(BudFormContext);

  return (
    <BudDrawerFooter>
      {props.onBack && props.showBack
        ? <SecondaryButton
          onClick={props.onBack}
          disabled={props.disableBack}
        >
          {props.backText || "Back"}
        </SecondaryButton>
        :
        <div />
      }
      {props.onNext
        ? <PrimaryButton
          htmlType="submit"
          disabled={props.disableNext}
          id="next-button"
        >
          {props.nextText || "Next"}
        </PrimaryButton>
        :
        <div />
      }

    </BudDrawerFooter>
  );
}

export interface BudFormProps extends FooterProps {
  data: any;
  children: React.ReactNode;
  title?: string;
  drawerLoading?: boolean;
  onValuesChange?: (changedValues: any, allValues: any) => void;
}


export function BudForm(props: BudFormProps) {
  const { deleteWorkflow } = useDeployModel();
  const { currentWorkflow, loading } = useDeployModel();
  const { currentWorkflow:performanceCurrentWorkflow, loading: performanceLoading, deleteWorkflow :performanceDeleteWorkflow} = usePerfomanceBenchmark();

  const { step, cancelAlert, setCancelAlert, closeDrawer, closeExpandedStep, expandedStep } = useDrawer();
  const { form, isExpandedView } = useContext(BudFormContext);

  useEffect(() => {
    // Only set form values if we have actual data (not empty object)
    if (props.data && Object.keys(props.data).length > 0) {
      // Get current form values
      const currentValues = form.getFieldsValue();

      // Check if values are actually different
      const hasChanges = Object.keys(props.data).some(key => {
        // Using JSON.stringify for a simple deep comparison. This is safer than reference equality for objects/arrays.
        // For complex cases, a library like `lodash.isEqual` would be more robust.
        return JSON.stringify(props.data[key]) !== JSON.stringify(currentValues[key]);
      });

      // Only update if there are actual changes
      if (hasChanges) {
        form.setFieldsValue(props.data);
      }
    }
  }, [props.data, form]);

  // Don't reset fields on unmount - we want to preserve form data when navigating
  // The form will be properly initialized with data prop when remounting

  useEffect(() => {
    if (cancelAlert) {
      document.getElementsByClassName('BudWraperBox')[0]?.classList.add('blur');
    } else {
      document.getElementsByClassName('BudWraperBox')[0]?.classList.remove('blur');
    }
  }, [cancelAlert]);

  return <Form
    form={form}
    validateTrigger={["onBlur", "onSubmit"]}
    // Blur logic
    className={`flex flex-col h-full  relative` }
    scrollToFirstError
    onValuesChange={props.onValuesChange}
    feedbackIcons={() => {
      // return <FeedbackIcons status={status} errors={errors} warnings={warnings} />
      return {
        error: <Image src="/icons/warning.svg" alt="error" width={"1rem"} height={"1rem"} />,
        success: <div />,
        warning: <div />,
        "": <div />,
      }
    }}
    onFinish={(values) => {
      if (isExpandedView) {
        closeExpandedStep();
      } else if (props.onNext) {
        props.onNext(values);
      }
    }}
  >
    {(loading || performanceLoading || props.drawerLoading) && <div className="flex items-center justify-center h-full w-full absolute bg-opacity-50  z-[100000000000000]">
      <Spin />
    </div>}
    {isExpandedView ? <div
      className="ant-header-breadcrumb"
    >
      <Text_12_400_5B6168 className="h-[18px] py-[.7rem]"></Text_12_400_5B6168>
    </div> : <DrawerBreadCrumbNavigation items={step.navigation} />}
    {isExpandedView ? null : cancelAlert && (<div className={`flex-initial z-20 border-1 border-[red] form-layout !mb-[0] top-[1rem] relative`}>
      <BudStepAlert
        cancelAction={() => {
          setCancelAlert(false);
        }}
        title="Are you sure you want to cancel?"
        description="You will lose all progress on this flow."
        confirmAction={async () => {
          if (currentWorkflow?.workflow_id) {
            await deleteWorkflow(currentWorkflow.workflow_id);
          }
          if (performanceCurrentWorkflow?.workflow_id) {
            await performanceDeleteWorkflow(performanceCurrentWorkflow?.workflow_id);
          }
          closeDrawer();
          setCancelAlert(false);
        }}
        confirmText="Yes, cancel"
        cancelText="No, keep working"
        type="warining"

      />
    </div>)}

    {props.children}
    {isExpandedView ?
      <Footer
        nextText={'Close'}
        onNext={() => {
          closeExpandedStep();
        }}
      />
      : <Footer
        backText={props.backText}
        nextText={props.nextText}
        onBack={props.onBack}
        onNext={props.onNext}
        disableNext={props.disableNext}
        disableBack={props.disableBack}
        showBack={props.showBack !== false}
      />}
  </Form>
}
