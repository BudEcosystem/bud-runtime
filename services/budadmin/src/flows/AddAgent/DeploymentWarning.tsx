import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_12_400_757575, Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";
import { errorToast } from "@/components/toast";
import { Alert } from "antd";
import { useAddAgent } from "@/stores/useAddAgent";

export default function DeploymentWarning() {
  const { openDrawerWithStep } = useDrawer();
  const [loading, setLoading] = useState(false);

  // Get data from the Add Agent store
  const {
    selectedProject,
    selectedModel,
    deploymentConfiguration,
    warningData,
    setWarningData,
  } = useAddAgent();

  const handleNext = async () => {
    setLoading(true);
    try {
      // Clear the warning data as user has acknowledged it
      setWarningData(null);

      // Navigate to success screen
      openDrawerWithStep("add-agent-success");

    } catch (error) {
      console.error("Failed to proceed:", error);
      errorToast("Failed to proceed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-configuration");
  };

  // Get warning/error details
  const hasWarnings = warningData?.warnings && warningData.warnings.length > 0;
  const hasErrors = warningData?.errors && warningData.errors.length > 0;
  const hasValidationIssues = warningData?.validation_issues && warningData.validation_issues.length > 0;

  // Build display message based on actual warnings/errors
  const getWarningMessage = () => {
    if (warningData?.warnings && warningData.warnings.length > 0) {
      return warningData.warnings.join(" ");
    }

    // Fallback to default warning message if no specific warnings
    const concurrentRequests = deploymentConfiguration?.maxConcurrency || 10;
    const deploymentName = selectedModel?.name || "the model";
    return `The deployment is configured with ${concurrentRequests} concurrent requests and auto-scale settings which may not be sufficient to support the given concurrency for the prompt. Consider adjusting the max replica settings for ${deploymentName} deployment auto-scaling.`;
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText={loading ? "Proceeding..." : "Proceed Anyway"}
      disableNext={loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="px-[1.35rem] pt-[1.5rem] pb-[1.35rem]">
            {/* Warning/Error Header */}
            <div style={{ display: "flex", alignItems: "flex-start" }}>
              <img
                src={hasErrors ? "/images/drawer/error.png" : "/images/drawer/warning.png"}
                alt={hasErrors ? "Error" : "Warning"}
                style={{
                  width: "55px",
                  marginRight: 24,
                  marginLeft: 6,
                  marginTop: 11,
                }}
              />
              <div className="flex flex-col gap-y-[12px] pt-[5px] flex-1">
                <Text_14_600_EEEEEE>
                  {hasErrors ? "Configuration Errors" : "Configuration Warnings"}
                </Text_14_600_EEEEEE>

                {/* Display warnings */}
                {hasWarnings && (
                  <div className="space-y-2">
                    {warningData.warnings.map((warning: string, index: number) => (
                      <Alert
                        key={`warning-${index}`}
                        message={warning}
                        type="warning"
                        showIcon
                        className="bg-yellow-900/20 border-yellow-600/30"
                      />
                    ))}
                  </div>
                )}

                {/* Display errors */}
                {hasErrors && (
                  <div className="space-y-2">
                    {warningData.errors.map((error: string, index: number) => (
                      <Alert
                        key={`error-${index}`}
                        message={error}
                        type="error"
                        showIcon
                        className="bg-red-900/20 border-red-600/30"
                      />
                    ))}
                  </div>
                )}

                {/* Display validation issues */}
                {hasValidationIssues && (
                  <div className="space-y-2">
                    {warningData.validation_issues.map((issue: string, index: number) => (
                      <Alert
                        key={`validation-${index}`}
                        message={issue}
                        type="info"
                        showIcon
                        className="bg-blue-900/20 border-blue-600/30"
                      />
                    ))}
                  </div>
                )}

                {/* Display recommendations if available */}
                {warningData?.recommendations && Object.keys(warningData.recommendations).length > 0 && (
                  <div className="mt-4">
                    <Text_14_400_EEEEEE className="mb-2">Recommendations:</Text_14_400_EEEEEE>
                    <div className="space-y-1">
                      {Object.entries(warningData.recommendations).map(([key, value]: [string, any]) => (
                        <Text_12_400_757575 key={key}>
                          • {key}: {value}
                        </Text_12_400_757575>
                      ))}
                    </div>
                  </div>
                )}

                {/* Fallback message if no specific warnings/errors */}
                {!hasWarnings && !hasErrors && !hasValidationIssues && (
                  <Text_12_400_757575>{getWarningMessage()}</Text_12_400_757575>
                )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
