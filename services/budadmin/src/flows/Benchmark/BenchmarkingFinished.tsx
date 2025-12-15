import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useRouter } from "next/router";
import { useDrawer } from "src/hooks/useDrawer";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { Image } from "antd";
import { Text_12_400_B3B3B3, Text_24_600_EEEEEE } from "@/components/ui/text";

export default function BenchmarkingFinished() {
  const router = useRouter();
  const { currentWorkflow } = usePerfomanceBenchmark();
  const { closeDrawer } = useDrawer();

  const handleViewReport = () => {
    const benchmarkId = (currentWorkflow?.workflow_steps as any)?.benchmark_id;
    closeDrawer();
    if (benchmarkId) {
      router.push(`/modelRepo/benchmarks-history/${benchmarkId}`);
    }
  };

  return (
    <BudForm
      data={{}}
      onNext={handleViewReport}
      nextText="View Report"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col	justify-start items-center p-[2.5rem] pt-[5.5rem]">
            <div className="align-center">
              <Image
                preview={false}
                src="/images/successHand.png"
                alt="info"
                width={140}
                height={129}
              />
            </div>
            <div className="mt-[1.3rem] mb-[3rem] w-full flex justify-center items-center flex-col	">
              <Text_24_600_EEEEEE className="text-center leading-[2rem] mb-[1.2rem] max-w-[70%]">
                Benchmark successful
              </Text_24_600_EEEEEE>
              <Text_12_400_B3B3B3 className="text-center leading-[1.125rem] max-w-[85%]">
                We have successfully completed the benchmark, please view the
                report for the details
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
