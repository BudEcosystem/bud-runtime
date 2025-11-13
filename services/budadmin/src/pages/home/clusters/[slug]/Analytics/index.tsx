"use client";
import { Card, Col, Row, Spin, Statistic, Table, message } from "antd";
import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { AppRequest } from "src/pages/api/requests";
import { CloudServerOutlined, DatabaseOutlined, DashboardOutlined, HeartOutlined } from "@ant-design/icons";

interface GeneralProps {
  cluster_id: string;
}

interface MetricsSummary {
  total_nodes: number;
  total_pods: number;
  avg_cpu_usage: number;
  avg_memory_usage: number;
  avg_disk_usage: number;
  health_status: string;
}

interface NodeMetric {
  node_name: string;
  cpu_usage_percent: number;
  memory_usage_percent: number;
  disk_usage_percent: number;
  cpu_cores: number;
  memory_total_gb: number;
  disk_total_gb: number;
  load_1: number;
  load_5: number;
  load_15: number;
}

interface PodMetric {
  namespace: string;
  pod_name: string;
  container_name: string;
  cpu_usage: number;
  memory_usage_mb: number;
  status: string;
  restarts: number;
}

const Analytics: React.FC<GeneralProps> = ({ cluster_id }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [nodeMetrics, setNodeMetrics] = useState<NodeMetric[]>([]);
  const [podMetrics, setPodMetrics] = useState<PodMetric[]>([]);
  const [timeSeriesData, setTimeSeriesData] = useState<any[]>([]);

  useEffect(() => {
    if (cluster_id) {
      fetchMetrics();
      // Refresh metrics every 30 seconds
      const interval = setInterval(fetchMetrics, 30000);
      return () => clearInterval(interval);
    }
  }, [cluster_id]);

  const fetchMetrics = async () => {
    try {
      setIsLoading(true);

      // Fetch summary
      const summaryRes = await AppRequest.Get(`/clusters/${cluster_id}/metrics/summary`);
      if (summaryRes.data) {
        setSummary(summaryRes.data);
      }

      // Fetch node metrics
      const nodesRes = await AppRequest.Get(`/clusters/${cluster_id}/metrics/nodes`);
      if (nodesRes.data && nodesRes.data.metrics) {
        setNodeMetrics(nodesRes.data.metrics);

        // Transform node metrics for time series chart
        const tsData = nodesRes.data.metrics.map((node: NodeMetric) => ({
          name: node.node_name.split('.')[0], // Shorten node names
          CPU: node.cpu_usage_percent.toFixed(1),
          Memory: node.memory_usage_percent.toFixed(1),
          Disk: node.disk_usage_percent.toFixed(1),
        }));
        setTimeSeriesData(tsData);
      }

      // Fetch pod metrics
      const podsRes = await AppRequest.Get(`/clusters/${cluster_id}/metrics/pods`);
      if (podsRes.data && podsRes.data.metrics) {
        setPodMetrics(podsRes.data.metrics);
      }
    } catch (error: any) {
      console.error("Error fetching metrics:", error);
      message.error("Failed to fetch cluster metrics");
    } finally {
      setIsLoading(false);
    }
  };

  const nodeColumns = [
    {
      title: "Node Name",
      dataIndex: "node_name",
      key: "node_name",
      render: (text: string) => text.split('.')[0],
    },
    {
      title: "CPU Usage",
      dataIndex: "cpu_usage_percent",
      key: "cpu_usage_percent",
      render: (value: number) => (
        <span style={{ color: value > 80 ? 'red' : value > 60 ? 'orange' : 'green' }}>
          {value.toFixed(1)}%
        </span>
      ),
      sorter: (a: NodeMetric, b: NodeMetric) => a.cpu_usage_percent - b.cpu_usage_percent,
    },
    {
      title: "Memory Usage",
      dataIndex: "memory_usage_percent",
      key: "memory_usage_percent",
      render: (value: number) => (
        <span style={{ color: value > 80 ? 'red' : value > 60 ? 'orange' : 'green' }}>
          {value.toFixed(1)}%
        </span>
      ),
      sorter: (a: NodeMetric, b: NodeMetric) => a.memory_usage_percent - b.memory_usage_percent,
    },
    {
      title: "Disk Usage",
      dataIndex: "disk_usage_percent",
      key: "disk_usage_percent",
      render: (value: number) => (
        <span style={{ color: value > 80 ? 'red' : value > 60 ? 'orange' : 'green' }}>
          {value.toFixed(1)}%
        </span>
      ),
      sorter: (a: NodeMetric, b: NodeMetric) => a.disk_usage_percent - b.disk_usage_percent,
    },
    {
      title: "CPU Cores",
      dataIndex: "cpu_cores",
      key: "cpu_cores",
    },
    {
      title: "Memory (GB)",
      dataIndex: "memory_total_gb",
      key: "memory_total_gb",
      render: (value: number) => value.toFixed(1),
    },
    {
      title: "Load Average",
      key: "load",
      render: (record: NodeMetric) => (
        <span>{record.load_1.toFixed(2)} / {record.load_5.toFixed(2)} / {record.load_15.toFixed(2)}</span>
      ),
    },
  ];

  const podColumns = [
    {
      title: "Namespace",
      dataIndex: "namespace",
      key: "namespace",
    },
    {
      title: "Pod Name",
      dataIndex: "pod_name",
      key: "pod_name",
      render: (text: string) => text.length > 40 ? text.substring(0, 37) + '...' : text,
    },
    {
      title: "Container",
      dataIndex: "container_name",
      key: "container_name",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <span style={{
          color: status === 'Running' ? 'green' : status === 'Pending' ? 'orange' : 'red',
          fontWeight: 'bold'
        }}>
          {status}
        </span>
      ),
    },
    {
      title: "CPU Usage",
      dataIndex: "cpu_usage",
      key: "cpu_usage",
      render: (value: number) => value.toFixed(3),
      sorter: (a: PodMetric, b: PodMetric) => a.cpu_usage - b.cpu_usage,
    },
    {
      title: "Memory (MB)",
      dataIndex: "memory_usage_mb",
      key: "memory_usage_mb",
      render: (value: number) => value.toFixed(1),
      sorter: (a: PodMetric, b: PodMetric) => a.memory_usage_mb - b.memory_usage_mb,
    },
    {
      title: "Restarts",
      dataIndex: "restarts",
      key: "restarts",
      render: (value: number) => (
        <span style={{ color: value > 5 ? 'red' : value > 0 ? 'orange' : 'green' }}>
          {value}
        </span>
      ),
      sorter: (a: PodMetric, b: PodMetric) => a.restarts - b.restarts,
    },
  ];

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="Total Nodes"
                value={summary.total_nodes}
                prefix={<CloudServerOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="Total Pods"
                value={summary.total_pods}
                prefix={<DatabaseOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="Avg CPU Usage"
                value={summary.avg_cpu_usage}
                suffix="%"
                prefix={<DashboardOutlined />}
                valueStyle={{ color: summary.avg_cpu_usage > 80 ? '#cf1322' : '#3f8600' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="Health Status"
                value={summary.health_status}
                prefix={<HeartOutlined />}
                valueStyle={{
                  color: summary.health_status === 'Healthy' ? '#3f8600' :
                         summary.health_status === 'Warning' ? '#fa8c16' : '#cf1322'
                }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Resource Usage Chart */}
      {timeSeriesData.length > 0 && (
        <Card title="Node Resource Usage">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={timeSeriesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis label={{ value: 'Usage (%)', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="CPU" fill="#1890ff" />
              <Bar dataKey="Memory" fill="#52c41a" />
              <Bar dataKey="Disk" fill="#fa8c16" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Node Metrics Table */}
      <Card title="Node Metrics">
        <Table
          dataSource={nodeMetrics}
          columns={nodeColumns}
          rowKey="node_name"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 800 }}
        />
      </Card>

      {/* Pod Metrics Table */}
      <Card title="Pod Metrics">
        <Table
          dataSource={podMetrics}
          columns={podColumns}
          rowKey={(record) => `${record.namespace}-${record.pod_name}-${record.container_name}`}
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  );
};

export default Analytics;
