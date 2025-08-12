import React from 'react';
import { Card, Row, Col, Statistic, Progress, List, Empty, Spin, Tag } from 'antd';
import {
  SecurityScanOutlined,
  StopOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  FireOutlined,
  RiseOutlined
} from '@ant-design/icons';
import { BlockingStats } from '@/stores/useBlockingRules';
import { Text_12_400_808080, Text_14_600_EEEEEE } from '@/components/ui/text';

interface BlockingRuleStatsProps {
  stats: BlockingStats | null;
  isLoading: boolean;
}

const BlockingRuleStats: React.FC<BlockingRuleStatsProps> = ({ stats, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-32">
        <Spin size="large" />
      </div>
    );
  }

  if (!stats) {
    return (
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card className="bg-[#1A1A1A] border-gray-800">
            <Empty
              description="No statistics available"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          </Card>
        </Col>
      </Row>
    );
  }

  const ruleTypeDistribution = stats.blocks_by_type
    ? Object.entries(stats.blocks_by_type).map(([type, count]) => ({
        type,
        count,
        percent: stats.total_rules ? (count / stats.total_rules) * 100 : 0,
      }))
    : [];

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'IP_BLOCKING':
        return '#ef4444';
      case 'COUNTRY_BLOCKING':
        return '#3b82f6';
      case 'USER_AGENT_BLOCKING':
        return '#f59e0b';
      case 'RATE_BASED_BLOCKING':
        return '#10b981';
      default:
        return '#6b7280';
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'IP_BLOCKING':
        return 'IP Blocking';
      case 'COUNTRY_BLOCKING':
        return 'Country';
      case 'USER_AGENT_BLOCKING':
        return 'User Agent';
      case 'RATE_BASED_BLOCKING':
        return 'Rate Limit';
      default:
        return type;
    }
  };

  return (
    <div className="blockingRuleStats">
      <Row gutter={[16, 16]}>
        {/* Main Statistics Cards */}
        <Col xs={24} sm={12} md={6}>
          <Card className="bg-[#1A1A1A] border-gray-800">
            <Statistic
              title={<Text_12_400_808080>Total Rules</Text_12_400_808080>}
              value={stats.total_rules || 0}
              prefix={<SecurityScanOutlined style={{ color: '#965CDE' }} />}
              valueStyle={{ color: '#EEEEEE' }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card className="bg-[#1A1A1A] border-gray-800">
            <Statistic
              title={<Text_12_400_808080>Active Rules</Text_12_400_808080>}
              value={stats.active_rules || 0}
              prefix={<CheckCircleOutlined style={{ color: '#10b981' }} />}
              valueStyle={{ color: '#10b981' }}
            />
            <Progress
              percent={stats.total_rules ? (stats.active_rules / stats.total_rules) * 100 : 0}
              showInfo={false}
              strokeColor="#10b981"
              trailColor="#374151"
              size="small"
              className="mt-2"
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card className="bg-[#1A1A1A] border-gray-800">
            <Statistic
              title={<Text_12_400_808080>Blocks Today</Text_12_400_808080>}
              value={stats.total_blocks_today || 0}
              prefix={<StopOutlined style={{ color: '#ef4444' }} />}
              valueStyle={{ color: '#ef4444' }}
              suffix={
                stats.total_blocks_week && stats.total_blocks_week > 0 ? (
                  <span className="text-xs text-gray-500">
                    / {stats.total_blocks_week} week
                  </span>
                ) : null
              }
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Card className="bg-[#1A1A1A] border-gray-800">
            <Statistic
              title={<Text_12_400_808080>Inactive Rules</Text_12_400_808080>}
              value={stats.inactive_rules || 0}
              prefix={<CloseCircleOutlined style={{ color: '#6b7280' }} />}
              valueStyle={{ color: '#6b7280' }}
            />
            {stats.expired_rules > 0 && (
              <div className="mt-2">
                <Tag color="warning" className="text-xs">
                  <ClockCircleOutlined /> {stats.expired_rules} Expired
                </Tag>
              </div>
            )}
          </Card>
        </Col>

        {/* Rule Type Distribution */}
        <Col xs={24} md={12}>
          <Card
            className="bg-[#1A1A1A] border-gray-800"
            title={<Text_14_600_EEEEEE>Rules by Type</Text_14_600_EEEEEE>}
          >
            {ruleTypeDistribution.length > 0 ? (
              <div className="space-y-3">
                {ruleTypeDistribution.map((item) => (
                  <div key={item.type} className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Tag color={getTypeColor(item.type)} style={{ margin: 0 }}>
                        {getTypeLabel(item.type)}
                      </Tag>
                      <Text_12_400_808080>{item.count} rules</Text_12_400_808080>
                    </span>
                    <Progress
                      percent={item.percent}
                      size="small"
                      strokeColor={getTypeColor(item.type)}
                      trailColor="#374151"
                      style={{ width: 100 }}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                description="No rule distribution data"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )}
          </Card>
        </Col>

        {/* Top Blocked IPs */}
        <Col xs={24} md={6}>
          <Card
            className="bg-[#1A1A1A] border-gray-800"
            title={
              <span className="flex items-center gap-2">
                <FireOutlined style={{ color: '#ef4444' }} />
                <Text_14_600_EEEEEE>Top Blocked IPs</Text_14_600_EEEEEE>
              </span>
            }
          >
            {stats.top_blocked_ips && stats.top_blocked_ips.length > 0 ? (
              <List
                size="small"
                dataSource={stats.top_blocked_ips.slice(0, 5)}
                renderItem={(item) => (
                  <List.Item className="border-gray-700">
                    <div className="flex justify-between w-full">
                      <Text_12_400_808080 className="font-mono">
                        {item.ip}
                      </Text_12_400_808080>
                      <Tag color="red" style={{ margin: 0 }}>
                        {item.count}
                      </Tag>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty
                description="No blocked IPs"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )}
          </Card>
        </Col>

        {/* Top Blocked Countries */}
        <Col xs={24} md={6}>
          <Card
            className="bg-[#1A1A1A] border-gray-800"
            title={
              <span className="flex items-center gap-2">
                <GlobalOutlined style={{ color: '#3b82f6' }} />
                <Text_14_600_EEEEEE>Top Blocked Countries</Text_14_600_EEEEEE>
              </span>
            }
          >
            {stats.top_blocked_countries && stats.top_blocked_countries.length > 0 ? (
              <List
                size="small"
                dataSource={stats.top_blocked_countries.slice(0, 5)}
                renderItem={(item) => (
                  <List.Item className="border-gray-700">
                    <div className="flex justify-between w-full">
                      <Text_12_400_808080>
                        {item.country}
                      </Text_12_400_808080>
                      <Tag color="blue" style={{ margin: 0 }}>
                        {item.count}
                      </Tag>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty
                description="No blocked countries"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default BlockingRuleStats;
