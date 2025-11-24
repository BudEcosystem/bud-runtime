import React from 'react';
import { useGuardrails } from '@/stores/useGuardrails';
import { Text_12_400_B3B3B3, Text_26_600_FFFFFF, Text_14_600_EEEEEE, Text_20_400_FFFFFF } from '@/components/ui/text';
import { ClientTimestamp } from '@/components/ui/ClientTimestamp';
import Tags from 'src/flows/components/DrawerTags';
import ProjectTags from 'src/flows/components/ProjectTags';
import { capitalize } from '@/lib/utils';
import { Row, Col } from 'antd';

const GeneralTab = () => {
  const { selectedGuardrail } = useGuardrails();

  if (!selectedGuardrail) return null;

  const getGuardTypeColor = (type: string) => {
    const colors = [
      '#3B82F6', // blue
      '#8B5CF6', // purple
      '#EC4899', // pink
      '#14B8A6', // teal
      '#F59E0B', // amber
    ];
    const index = type.length % colors.length;
    return colors[index];
  };

  const getStatusConfig = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return { color: '#479d5f', label: 'Active' };
      case 'inactive':
        return { color: '#F59E0B', label: 'Inactive' };
      case 'draft':
        return { color: '#6B7280', label: 'Draft' };
      default:
        return { color: '#6B7280', label: status || 'Unknown' };
    }
  };

  const statusConfig = getStatusConfig(selectedGuardrail.status);

  return (
    <div className="pb-8">
      {/* Guardrail Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2 pt-[.5rem]">
          <Text_26_600_FFFFFF className="text-[#EEE]">
            {selectedGuardrail.name}
          </Text_26_600_FFFFFF>
          <ProjectTags
            name={capitalize(statusConfig.label)}
            color={statusConfig.color}
          />
        </div>
        <Text_12_400_B3B3B3 className="max-w-[850px] mb-3">
          {selectedGuardrail.description || 'No description provided.'}
        </Text_12_400_B3B3B3>
        <div className="flex items-center gap-2 flex-wrap">
          {selectedGuardrail.tags && selectedGuardrail.tags.length > 0 && (
            selectedGuardrail.tags.map((tag: any, index: number) => (
              <Tags
                textClass="text-[.75rem]"
                key={index}
                name={tag.name}
                color={tag.color || '#d4B7DB'}
              />
            ))
          )}
        </div>
      </div>

      {/* Metrics / Details Grid */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
            <Text_12_400_B3B3B3 className="mb-2">Severity Threshold</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>{selectedGuardrail.severity_threshold ?? '-'}</Text_20_400_FFFFFF>
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
            <Text_12_400_B3B3B3 className="mb-2">Created At</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>
              <ClientTimestamp timestamp={selectedGuardrail.created_at} />
            </Text_20_400_FFFFFF>
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
            <Text_12_400_B3B3B3 className="mb-2">Modified At</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>
              <ClientTimestamp timestamp={selectedGuardrail.modified_at || selectedGuardrail.created_at} />
            </Text_20_400_FFFFFF>
          </div>
        </Col>
      </Row>

      {/* Guard Types Section */}
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
        <div className="mb-4">
          <Text_14_600_EEEEEE>Guard Types</Text_14_600_EEEEEE>
          <Text_12_400_B3B3B3 className="block mt-1">Types of protection enabled for this guardrail</Text_12_400_B3B3B3>
        </div>
        <div className="flex flex-wrap gap-2">
          {selectedGuardrail.guard_types && selectedGuardrail.guard_types.length > 0 ? (
            selectedGuardrail.guard_types.map((type: string, index: number) => (
              <Tags
                key={index}
                name={type}
                color={getGuardTypeColor(type)}
              />
            ))
          ) : (
            <Text_12_400_B3B3B3>No guard types configured</Text_12_400_B3B3B3>
          )}
        </div>
      </div>
    </div>
  );
};

export default GeneralTab;
