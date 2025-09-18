import React, { useEffect, useState } from "react";
import { Text_14_600_EEEEEE } from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import { LeaderBoardItem, Model, useModels } from "src/hooks/useModels";
import LeaderboardsTable from "@/components/ui/bud/table/LeaderboardsTable";

export interface BudInputProps {
  ClassNames?: string;
  leaderboardClasses?: string;
  showHeader?: boolean;
  runEval?: boolean;
  model: Model;
}

function Leaderboards({
  ClassNames = "",
  leaderboardClasses = "",
  showHeader = true,
  runEval,
  model,
}: BudInputProps) {
  const [leaderboards, setLeaderBoards] = useState<LeaderBoardItem[]>([]);
  const { openDrawerWithStep } = useDrawer();
  const { getLeaderBoard } = useModels();

  useEffect(() => {
    if (model?.id) {
      getLeaderBoard(model?.id).then((res) => {
        setLeaderBoards(res);
      });
    }
  }, [model?.id]);

  return (
    <div className={`${ClassNames}`}>
      {showHeader && (
        <div className="flex justify-between items-center">
          <Text_14_600_EEEEEE className="leading-[1.125rem]">
            Leaderboards
          </Text_14_600_EEEEEE>
          {runEval && (
            <PrimaryButton
              type="submit"
              onClick={() => {
                openDrawerWithStep("select-model-evaluations");
              }}
              className="min-w-[7.7rem]"
            >
              Run Evaluations
            </PrimaryButton>
          )}
        </div>
      )}
      <LeaderboardsTable
        data={leaderboards}
        leaderboardClasses={leaderboardClasses}
      />
    </div>
  );
}

export default Leaderboards;
