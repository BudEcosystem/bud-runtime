import { Tooltip } from "antd";
import { BudSimulatorSteps } from "src/stores/useDeployModel";

function ProgressWithBud({
  progress = 0,
  title,
  showBud = false,
  overallProgress,
  isFailed,
}: {
  progress: number;
  title?: string;
  showBud?: boolean;
  overallProgress: number;
  isFailed?: boolean;
}) {
  return (
    <div className="show-container mr-[.4rem]">
      <div className="progress" id="progressBar">
        {showBud && (
          <div
            className={`progress-number ${isFailed && "failed"}`}
            data-content={`${overallProgress}%`}
            style={{ left: `${progress}%` }}
          >
            <img
              src={isFailed ? "/gifs/failed-bud.svg" : "/gifs/loading-bud.gif"}
              alt="progress"
              style={{
                width: "1rem",
                height: "1rem",
                transform: "translate(-50%, -50%)",
              }}
            />
          </div>
        )}
        {/* <Tooltip title={title} color="#1F1F1F" placement="top" > */}
        <div className="rounded cursor-pointer">
          <div
            className={`progress-bar ${isFailed && "failed"}`}
            style={{
              width: `${progress}%`,
            }}
          ></div>
        </div>
        {/* </Tooltip> */}
      </div>
    </div>
  );
}

export function ProgressWithBudList({
  events = [],
}: {
  events: BudSimulatorSteps[];
}) {
  const completedEvents = events?.filter(
    (event) => event?.payload?.content?.status === "COMPLETED",
  );
  const overallProgress = Math.round(
    (completedEvents?.length / events?.length) * 100,
  );
  const failedEvents = events?.filter(
    (event) => event?.payload?.content?.status === "FAILED",
  );

  // sort events by completed status
  const sortedEvents = [...events].sort((a, b) => {
    if (
      a?.payload?.content?.status === "COMPLETED" &&
      b?.payload?.content?.status !== "COMPLETED"
    ) {
      return -1;
    } else if (
      a?.payload?.content?.status !== "COMPLETED" &&
      b?.payload?.content?.status === "COMPLETED"
    ) {
      return 1;
    }
    return 0;
  });

  return (
    <div className="deploymentProgress w-full px-[1.35rem] pt-[.3rem] mb-6 flex justify-between items-center mt-[2.3rem]">
      {sortedEvents?.map((event, index) => {
        return (
          <ProgressWithBud
            progress={event?.payload?.content?.status === "COMPLETED" ? 100 : 0}
            key={index}
            showBud={completedEvents.length === index}
            isFailed={failedEvents.length > 0}
            overallProgress={overallProgress}
            title={event?.title}
          />
        );
      })}
    </div>
  );
}
