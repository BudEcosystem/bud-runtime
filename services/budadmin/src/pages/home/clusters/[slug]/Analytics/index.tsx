"use client";
import { Spin } from "antd";
import { useEffect, useState } from "react";
import { useCluster } from "src/hooks/useCluster";
interface GeneralProps {
  cluster_id: string;
}

const Analytics: React.FC<GeneralProps> = ({ cluster_id }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [dashboardUrl, setDashboardUrl] = useState("");
  const { getClusterAnalytics } = useCluster();

  useEffect(() => {
    if (cluster_id) {
      getClusterAnalytics(cluster_id)
        .then((res) => {
          setDashboardUrl(res.url);
          setIsLoading(false);
        })
        .catch((error) => {
          console.error("Error getting cluster analytics:", error);
        });
    }
  }, [cluster_id]);

  return (
    <div className="">
      {/* <iframe src="https://grafana.bud.studio/public-dashboards/659a725c6ea54223b6642934eb82d57d" className="w-full h-[80vh] rounded" /> */}
      {isLoading || dashboardUrl.length === 0 ? (
        <div className="flex justify-center items-center h-full">
          <Spin />
        </div>
      ) : (
        <iframe src={dashboardUrl} className="w-full h-[80vh] rounded" />
      )}
    </div>
  );
};

export default Analytics;
