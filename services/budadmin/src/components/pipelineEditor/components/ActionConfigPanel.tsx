'use client';

/**
 * Action Config Panel
 *
 * Panel for editing workflow step parameters when a node is selected.
 * Renders form fields based on the action's parameter schema.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Icon } from '@iconify/react';
import { Slider, ConfigProvider } from 'antd';
import { AppRequest } from 'src/pages/api/requests';
import { errorToast } from '@/components/toast';
import {
  getActionMeta,
  getActionParams,
  getDefaultParams,
  validateParams,
  type ParamDefinition,
  type SelectOption,
  type ConditionalBranch,
} from '../config/actionRegistry';

// ============================================================================
// Icon Mapping - Maps action icon names to iconify icon identifiers
// ============================================================================

const ICON_MAP: Record<string, string> = {
  // Model Operations
  'database-plus': 'ph:database-bold',
  'cloud-upload': 'ph:cloud-arrow-up-bold',
  'chart-bar': 'ph:chart-bar-bold',
  'trash': 'ph:trash-bold',

  // Cluster Operations
  'heart-pulse': 'ph:heartbeat-bold',
  'server-x': 'ph:x-circle-bold',
  'server-plus': 'ph:plus-circle-bold',

  // Deployment Operations
  'rocket': 'ph:rocket-launch-bold',
  'shield': 'ph:shield-bold',
  'trending-up': 'ph:trend-up-bold',
  'arrows-alt': 'ph:arrows-out-bold',

  // Integration Operations
  'globe': 'ph:globe-bold',
  'bell': 'ph:bell-bold',
  'link': 'ph:link-bold',

  // Simulation
  'beaker': 'ph:flask-bold',

  // Control Flow
  'note': 'ph:note-bold',
  'timer': 'ph:timer-bold',
  'clock': 'ph:clock-bold',
  'git-branch': 'ph:git-branch-bold',
  'swap': 'ph:swap-bold',
  'stack': 'ph:stack-bold',
  'arrow-square-out': 'ph:arrow-square-out-bold',
  'x-circle': 'ph:x-circle-bold',
};

// ============================================================================
// Branch Editor Styles
// ============================================================================

const branchEditorStyles: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const branchItemStyles: React.CSSProperties = {
  background: '#0a0a0a',
  border: '1px solid #333',
  borderRadius: '8px',
  padding: '12px',
};

const branchHeaderStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: '10px',
};

const branchLabelInputStyles: React.CSSProperties = {
  flex: 1,
  padding: '6px 10px',
  background: '#1a1a1a',
  border: '1px solid #333',
  borderRadius: '4px',
  color: '#fff',
  fontSize: '13px',
  fontWeight: 500,
  outline: 'none',
};

const branchRemoveButtonStyles: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#666',
  fontSize: '14px',
  cursor: 'pointer',
  padding: '4px 8px',
  marginLeft: '8px',
};

const branchFieldStyles: React.CSSProperties = {
  marginBottom: '10px',
};

const branchFieldLabelStyles: React.CSSProperties = {
  display: 'block',
  fontSize: '11px',
  color: '#888',
  marginBottom: '4px',
};

const branchConditionInputStyles: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  background: '#1a1a1a',
  border: '1px solid #333',
  borderRadius: '4px',
  color: '#fff',
  fontSize: '12px',
  fontFamily: 'monospace',
  outline: 'none',
  minHeight: '60px',
  resize: 'vertical',
};

const branchTargetSelectStyles: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  background: '#1a1a1a',
  border: '1px solid #333',
  borderRadius: '4px',
  color: '#fff',
  fontSize: '12px',
  outline: 'none',
  cursor: 'pointer',
};

const addBranchButtonStyles: React.CSSProperties = {
  width: '100%',
  padding: '10px',
  background: 'transparent',
  border: '1px dashed #444',
  borderRadius: '6px',
  color: '#888',
  fontSize: '13px',
  cursor: 'pointer',
  transition: 'all 0.2s',
};

// ============================================================================
// Branch Editor Component
// ============================================================================

interface BranchEditorProps {
  branches: ConditionalBranch[];
  onChange: (branches: ConditionalBranch[]) => void;
  availableSteps: Array<{ stepId: string; name: string }>;
}

function BranchEditor({ branches, onChange, availableSteps }: BranchEditorProps) {
  const addBranch = () => {
    onChange([
      ...branches,
      {
        id: `branch_${branches.length}`,
        label: `Branch ${branches.length + 1}`,
        condition: '',
        target_step: null,
      },
    ]);
  };

  const removeBranch = (index: number) => {
    onChange(branches.filter((_, i) => i !== index));
  };

  const updateBranch = (index: number, field: keyof ConditionalBranch, value: string | null) => {
    const updated = [...branches];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  return (
    <div style={branchEditorStyles}>
      {branches.map((branch, index) => (
        <div key={branch.id} style={branchItemStyles}>
          <div style={branchHeaderStyles}>
            <input
              type="text"
              value={branch.label}
              placeholder="Branch name"
              style={branchLabelInputStyles}
              onChange={(e) => updateBranch(index, 'label', e.target.value)}
            />
            {branches.length > 1 && (
              <button
                style={branchRemoveButtonStyles}
                onClick={() => removeBranch(index)}
                title="Remove branch"
              >
                ✕
              </button>
            )}
          </div>

          <div style={branchFieldStyles}>
            <label style={branchFieldLabelStyles}>Condition (Jinja2)</label>
            <textarea
              value={branch.condition}
              placeholder="{{ steps.health_check.outputs.status == 'healthy' }}"
              style={branchConditionInputStyles}
              onChange={(e) => updateBranch(index, 'condition', e.target.value)}
            />
          </div>

          <div style={branchFieldStyles}>
            <label style={branchFieldLabelStyles}>Target Step</label>
            <select
              value={branch.target_step || ''}
              style={branchTargetSelectStyles}
              onChange={(e) => updateBranch(index, 'target_step', e.target.value || null)}
            >
              <option value="">Select target step...</option>
              {availableSteps.map((step) => (
                <option key={step.stepId} value={step.stepId}>
                  {step.name || step.stepId}
                </option>
              ))}
            </select>
          </div>
        </div>
      ))}

      <button
        style={addBranchButtonStyles}
        onClick={addBranch}
        onMouseOver={(e) => {
          e.currentTarget.style.borderColor = '#666';
          e.currentTarget.style.color = '#aaa';
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.borderColor = '#444';
          e.currentTarget.style.color = '#888';
        }}
      >
        + Add Branch
      </button>
    </div>
  );
}

// ============================================================================
// Types
// ============================================================================

export interface ActionConfigPanelProps {
  /** The selected step data */
  stepId: string;
  stepName: string;
  action: string;
  params: Record<string, unknown>;
  condition?: string;
  /** Callback when parameters are updated */
  onUpdate: (updates: {
    name?: string;
    params?: Record<string, unknown>;
    condition?: string;
  }) => void;
  /** Callback to close the panel */
  onClose: () => void;
  /** Callback to delete the step */
  onDelete?: () => void;
  /** Data sources for ref fields */
  dataSources?: {
    models?: SelectOption[];
    clusters?: SelectOption[];
    projects?: SelectOption[];
    endpoints?: SelectOption[];
    providers?: SelectOption[];
    credentials?: SelectOption[];
  };
  /** Whether data sources are loading */
  loadingDataSources?: Set<string>;
  /** Available steps for branch target selection (excluding current step) */
  availableSteps?: Array<{ stepId: string; name: string }>;
}

// ============================================================================
// Styles
// ============================================================================

const panelStyles: React.CSSProperties = {
  position: 'absolute',
  right: '16px',
  top: '16px',
  bottom: '16px',
  width: '320px',
  maxHeight: 'calc(100vh - 140px)',
  background: '#0a0a0a',
  border: '1px solid #262626',
  borderRadius: '12px',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
  zIndex: 10,
};

const headerStyles: React.CSSProperties = {
  padding: '12px 16px',
  borderBottom: '1px solid #1a1a1a',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  background: '#0a0a0a',
  borderRadius: '12px 12px 0 0',
};

const headerTitleStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const headerIconStyles: React.CSSProperties = {
  fontSize: '18px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '28px',
  height: '28px',
  borderRadius: '6px',
  background: '#1a1a1a',
};

const headerTextStyles: React.CSSProperties = {
  fontSize: '14px',
  fontWeight: 600,
  color: '#fff',
};

const closeButtonStyles: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#666',
  fontSize: '18px',
  cursor: 'pointer',
  padding: '4px',
  lineHeight: 1,
};

const contentStyles: React.CSSProperties = {
  flex: 1,
  overflow: 'auto',
  padding: '16px',
  background: '#0a0a0a',
};

const sectionStyles: React.CSSProperties = {
  marginBottom: '20px',
};

const sectionTitleStyles: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 600,
  color: '#666',
  textTransform: 'uppercase',
  marginBottom: '12px',
  letterSpacing: '0.5px',
};

const fieldGroupStyles: React.CSSProperties = {
  marginBottom: '16px',
};

const labelStyles: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  color: '#aaa',
  marginBottom: '6px',
};

const requiredBadgeStyles: React.CSSProperties = {
  color: '#ff4d4f',
  marginLeft: '4px',
};

const inputStyles: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  background: '#0a0a0a',
  border: '1px solid #333',
  borderRadius: '6px',
  color: '#fff',
  fontSize: '13px',
  outline: 'none',
};

const textareaStyles: React.CSSProperties = {
  ...inputStyles,
  minHeight: '80px',
  resize: 'vertical',
  fontFamily: 'monospace',
};

const selectStyles: React.CSSProperties = {
  ...inputStyles,
  cursor: 'pointer',
  appearance: 'none',
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M3 4.5L6 7.5L9 4.5'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: '32px',
};

const checkboxContainerStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const checkboxStyles: React.CSSProperties = {
  width: '16px',
  height: '16px',
  cursor: 'pointer',
};

const helpTextStyles: React.CSSProperties = {
  fontSize: '11px',
  color: '#666',
  marginTop: '4px',
};

const footerStyles: React.CSSProperties = {
  padding: '12px 16px',
  borderTop: '1px solid #1a1a1a',
  display: 'flex',
  gap: '8px',
  background: '#080808',
  borderRadius: '0 0 12px 12px',
};

const buttonStyles: React.CSSProperties = {
  flex: 1,
  padding: '8px 16px',
  borderRadius: '6px',
  fontSize: '13px',
  fontWeight: 500,
  cursor: 'pointer',
  border: 'none',
};

const primaryButtonStyles: React.CSSProperties = {
  ...buttonStyles,
  background: '#965CDE',
  color: '#fff',
  border: '1px solid #965CDE',
  transition: 'all 0.2s',
};

const dangerButtonStyles: React.CSSProperties = {
  ...buttonStyles,
  background: 'transparent',
  color: '#ff4d4f',
  border: '1px solid #ff4d4f40',
  transition: 'all 0.2s',
};

// ============================================================================
// Component
// ============================================================================

export function ActionConfigPanel({
  stepId,
  stepName,
  action,
  params,
  condition,
  onUpdate,
  onClose,
  onDelete,
  dataSources = {},
  loadingDataSources = new Set(),
  availableSteps = [],
}: ActionConfigPanelProps) {
  // Get default params for this action and merge with provided params
  const defaultParams = useMemo(() => getDefaultParams(action), [action]);
  const mergedParams = useMemo(() => ({ ...defaultParams, ...params }), [defaultParams, params]);

  // Local state for form values
  const [localParams, setLocalParams] = useState<Record<string, unknown>>(mergedParams);
  const [localName, setLocalName] = useState(stepName);
  const [localCondition, setLocalCondition] = useState(condition || '');
  // Track which ref fields are in template mode (for dynamic references like {{ steps.x.outputs.y }})
  const [templateModeFields, setTemplateModeFields] = useState<Set<string>>(() => {
    // Initialize based on existing values - if value looks like a template, enable template mode
    const templateFields = new Set<string>();
    Object.entries(mergedParams).forEach(([key, value]) => {
      if (typeof value === 'string' && value.includes('{{')) {
        templateFields.add(key);
      }
    });
    return templateFields;
  });

  // Sync local state when props change (e.g., when selecting a different node)
  useEffect(() => {
    const newMergedParams = { ...getDefaultParams(action), ...params };
    setLocalParams(newMergedParams);
    setLocalName(stepName);
    setLocalCondition(condition || '');
    // Update template mode fields based on new params
    const templateFields = new Set<string>();
    Object.entries(newMergedParams).forEach(([key, value]) => {
      if (typeof value === 'string' && value.includes('{{')) {
        templateFields.add(key);
      }
    });
    setTemplateModeFields(templateFields);
  }, [stepId, action, params, stepName, condition]);

  // Get action metadata
  const actionMeta = getActionMeta(action);
  const paramDefs = getActionParams(action);

  // Check if a string is an emoji
  const isEmoji = (str: string): boolean => {
    if (!str || str.length === 0) return false;
    const codePoint = str.codePointAt(0);
    if (!codePoint) return false;
    return codePoint >= 0x1F300 || (codePoint >= 0x2600 && codePoint <= 0x27BF);
  };

  // Render icon helper
  const renderActionIcon = () => {
    const iconStr = actionMeta.icon || '';
    const iconColor = actionMeta.color || '#965cde';

    // Check if it's an emoji
    if (isEmoji(iconStr)) {
      return <span style={{ fontSize: '16px' }}>{iconStr}</span>;
    }

    // Check if we have a mapping
    const iconifyName = ICON_MAP[iconStr.toLowerCase()];
    if (iconifyName) {
      return <Icon icon={iconifyName} style={{ color: iconColor, width: 18, height: 18 }} />;
    }

    // Try as Phosphor icon
    if (iconStr && !iconStr.includes(':')) {
      return <Icon icon={`ph:${iconStr}-bold`} style={{ color: iconColor, width: 18, height: 18 }} />;
    }

    // If it contains a colon, use as-is
    if (iconStr && iconStr.includes(':')) {
      return <Icon icon={iconStr} style={{ color: iconColor, width: 18, height: 18 }} />;
    }

    // Fallback to gear icon
    return <Icon icon="ph:gear-bold" style={{ color: iconColor, width: 18, height: 18 }} />;
  };

  // Group parameters by group name
  const groupedParams = useMemo(() => {
    const groups: Record<string, ParamDefinition[]> = {};
    const ungrouped: ParamDefinition[] = [];

    paramDefs.forEach((param) => {
      if (param.group) {
        if (!groups[param.group]) groups[param.group] = [];
        groups[param.group].push(param);
      } else {
        ungrouped.push(param);
      }
    });

    return { groups, ungrouped };
  }, [paramDefs]);

  // Check if a param should be visible based on showWhen
  const isParamVisible = useCallback(
    (param: ParamDefinition): boolean => {
      if (!param.showWhen) return true;

      const { param: depParam, equals, notEquals } = param.showWhen;
      const depValue = localParams[depParam];

      if (equals !== undefined) return depValue === equals;
      if (notEquals !== undefined) return depValue !== notEquals;
      return true;
    },
    [localParams]
  );

  // Handle param change
  const handleParamChange = useCallback(
    (name: string, value: unknown) => {
      setLocalParams((prev) => ({ ...prev, [name]: value }));
    },
    []
  );

  // State for saving
  const [isSaving, setIsSaving] = useState(false);

  // Handle save
  // Show validation errors as a toast notification
  const showValidationErrors = useCallback((errors: string[]) => {
    const message = errors.length === 1
      ? errors[0]
      : `Validation failed: ${errors.join(', ')}`;
    errorToast(message);
  }, []);

  const handleSave = useCallback(async () => {
    // First do local validation
    const validation = validateParams(action, localParams);
    if (!validation.valid) {
      showValidationErrors(validation.errors);
      return;
    }

    setIsSaving(true);

    try {
      // Call backend validation API for conditional validation logic
      const response = await AppRequest.Post('/budpipeline/actions/validate', {
        action_type: action,
        params: localParams,
      });

      if (response?.data && !response.data.valid) {
        showValidationErrors(response.data.errors || ['Validation failed']);
        setIsSaving(false);
        return;
      }
    } catch (err) {
      // If validation API fails, log but continue (fallback to local validation)
      console.warn('Backend validation failed, using local validation only:', err);
    }

    setIsSaving(false);
    onUpdate({
      name: localName,
      params: localParams,
      condition: localCondition || undefined,
    });
    onClose();
  }, [action, localParams, localName, localCondition, onUpdate, onClose, showValidationErrors]);

  // Get options for ref types
  const getRefOptions = useCallback(
    (type: string): SelectOption[] => {
      switch (type) {
        case 'model_ref':
          return dataSources.models || [];
        case 'cluster_ref':
          return dataSources.clusters || [];
        case 'project_ref':
          return dataSources.projects || [];
        case 'endpoint_ref':
          return dataSources.endpoints || [];
        case 'provider_ref':
          return dataSources.providers || [];
        case 'credential_ref':
          return dataSources.credentials || [];
        default:
          return [];
      }
    },
    [dataSources]
  );

  // Check if loading ref type
  const isLoadingRef = useCallback(
    (type: string): boolean => {
      return loadingDataSources.has(type.replace('_ref', 's'));
    },
    [loadingDataSources]
  );

  // Toggle template mode for a ref field
  const toggleTemplateMode = useCallback((fieldName: string) => {
    setTemplateModeFields((prev) => {
      const next = new Set(prev);
      if (next.has(fieldName)) {
        next.delete(fieldName);
        // Clear the value when switching back to dropdown
        handleParamChange(fieldName, '');
      } else {
        next.add(fieldName);
        // Set a template placeholder when switching to template mode
        handleParamChange(fieldName, '{{ steps. }}');
      }
      return next;
    });
  }, [handleParamChange]);

  // Check if a field is in template mode
  const isTemplateMode = useCallback(
    (fieldName: string): boolean => templateModeFields.has(fieldName),
    [templateModeFields]
  );

  // Render a single field
  const renderField = useCallback(
    (param: ParamDefinition) => {
      if (!isParamVisible(param)) return null;

      const value = localParams[param.name] ?? param.default ?? '';
      const fieldId = `param-${param.name}`;

      return (
        <div key={param.name} style={fieldGroupStyles}>
          <label htmlFor={fieldId} style={labelStyles}>
            {param.label}
            {param.required && <span style={requiredBadgeStyles}>*</span>}
          </label>

          {/* String input */}
          {param.type === 'string' && (
            <input
              id={fieldId}
              type="text"
              value={String(value)}
              placeholder={param.placeholder}
              style={inputStyles}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
            />
          )}

          {/* Number input */}
          {param.type === 'number' && (
            <input
              id={fieldId}
              type="number"
              value={value !== '' ? Number(value) : ''}
              placeholder={param.placeholder}
              style={inputStyles}
              min={param.validation?.min}
              max={param.validation?.max}
              onChange={(e) =>
                handleParamChange(
                  param.name,
                  e.target.value === '' ? '' : Number(e.target.value)
                )
              }
            />
          )}

          {/* Boolean checkbox */}
          {param.type === 'boolean' && (
            <div style={checkboxContainerStyles}>
              <input
                id={fieldId}
                type="checkbox"
                checked={Boolean(value)}
                style={checkboxStyles}
                onChange={(e) => handleParamChange(param.name, e.target.checked)}
              />
              <span style={{ color: '#aaa', fontSize: '13px' }}>
                {param.description || 'Enable'}
              </span>
            </div>
          )}

          {/* Select dropdown */}
          {param.type === 'select' && (
            <select
              id={fieldId}
              value={String(value)}
              style={selectStyles}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
            >
              <option value="">Select...</option>
              {param.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}

          {/* Ref types (model, cluster, provider, credential, etc.) - with toggle for template mode */}
          {['model_ref', 'cluster_ref', 'project_ref', 'endpoint_ref', 'provider_ref', 'credential_ref'].includes(param.type) && (
            <div>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
                <button
                  type="button"
                  onClick={() => toggleTemplateMode(param.name)}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    background: isTemplateMode(param.name) ? '#1890ff' : '#333',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                  title={isTemplateMode(param.name) ? 'Switch to dropdown' : 'Use template expression'}
                >
                  {isTemplateMode(param.name) ? '📝 Template' : '📋 Select'}
                </button>
                {isTemplateMode(param.name) && (
                  <span style={{ fontSize: '10px', color: '#888', alignSelf: 'center' }}>
                    Reference output from previous step
                  </span>
                )}
              </div>
              {isTemplateMode(param.name) ? (
                <input
                  id={fieldId}
                  type="text"
                  value={String(value)}
                  placeholder={`{{ steps.prev_step.outputs.${param.name} }}`}
                  style={{ ...inputStyles, fontFamily: 'monospace', fontSize: '12px' }}
                  onChange={(e) => handleParamChange(param.name, e.target.value)}
                />
              ) : (
                <select
                  id={fieldId}
                  value={String(value)}
                  style={selectStyles}
                  disabled={isLoadingRef(param.type)}
                  onChange={(e) => handleParamChange(param.name, e.target.value)}
                >
                  <option value="">
                    {isLoadingRef(param.type) ? 'Loading...' : `Select ${param.label}...`}
                  </option>
                  {getRefOptions(param.type).map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Template (Jinja2) */}
          {param.type === 'template' && (
            <textarea
              id={fieldId}
              value={String(value)}
              placeholder={param.placeholder || '{{ steps.prev_step.outputs.value }}'}
              style={textareaStyles}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
            />
          )}

          {/* JSON input */}
          {param.type === 'json' && (
            <textarea
              id={fieldId}
              value={
                typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
              }
              placeholder={param.placeholder || '{}'}
              style={textareaStyles}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  handleParamChange(param.name, parsed);
                } catch {
                  handleParamChange(param.name, e.target.value);
                }
              }}
            />
          )}

          {/* Multiselect */}
          {param.type === 'multiselect' && (
            <select
              id={fieldId}
              multiple
              value={Array.isArray(value) ? value.map(String) : []}
              style={{ ...selectStyles, minHeight: '80px' }}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, (opt) => opt.value);
                handleParamChange(param.name, selected);
              }}
            >
              {param.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}

          {/* Range slider for performance targets */}
          {param.type === 'range' && (() => {
            const rangeValue = Array.isArray(value) ? value : (param.default as number[]) || [0, 100];
            const minVal = param.validation?.min ?? 0;
            const maxVal = param.validation?.max ?? 100;
            return (
              <ConfigProvider
                theme={{
                  components: {
                    Slider: {
                      trackBg: '#965CDE',
                      trackHoverBg: '#7A4BC7',
                      handleColor: '#965CDE',
                      handleActiveColor: '#7A4BC7',
                      dotActiveBorderColor: '#965CDE',
                      railBg: '#333',
                      railHoverBg: '#444',
                    },
                  },
                }}
              >
                <div style={{ padding: '8px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <input
                      type="number"
                      value={rangeValue[0] ?? minVal}
                      min={minVal}
                      max={rangeValue[1] ?? maxVal}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || minVal;
                        handleParamChange(param.name, [val, rangeValue[1] ?? maxVal]);
                      }}
                      style={{
                        ...inputStyles,
                        width: '70px',
                        textAlign: 'center',
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <Slider
                        range
                        min={minVal}
                        max={maxVal}
                        value={[rangeValue[0] ?? minVal, rangeValue[1] ?? maxVal]}
                        onChange={(vals) => handleParamChange(param.name, vals)}
                        tooltip={{
                          formatter: (val) => `${val}`,
                        }}
                      />
                    </div>
                    <input
                      type="number"
                      value={rangeValue[1] ?? maxVal}
                      min={rangeValue[0] ?? minVal}
                      max={maxVal}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || maxVal;
                        handleParamChange(param.name, [rangeValue[0] ?? minVal, val]);
                      }}
                      style={{
                        ...inputStyles,
                        width: '70px',
                        textAlign: 'center',
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                    <span style={{ fontSize: '10px', color: '#666' }}>{minVal}</span>
                    <span style={{ fontSize: '10px', color: '#666' }}>{maxVal}</span>
                  </div>
                </div>
              </ConfigProvider>
            );
          })()}

          {/* Branches (for conditional routing) */}
          {param.type === 'branches' && (
            <BranchEditor
              branches={
                Array.isArray(value)
                  ? (value as ConditionalBranch[])
                  : [{ id: 'branch_0', label: 'Branch 1', condition: '', target_step: null }]
              }
              onChange={(branches) => handleParamChange(param.name, branches)}
              availableSteps={availableSteps}
            />
          )}

          {/* Help text */}
          {param.description && param.type !== 'boolean' && (
            <div style={helpTextStyles}>{param.description}</div>
          )}
        </div>
      );
    },
    [localParams, isParamVisible, handleParamChange, getRefOptions, isLoadingRef, availableSteps, isTemplateMode, toggleTemplateMode]
  );

  return (
    <div style={panelStyles}>
      {/* Header */}
      <div style={headerStyles}>
        <div style={headerTitleStyles}>
          <span style={headerIconStyles}>{renderActionIcon()}</span>
          <span style={headerTextStyles}>{actionMeta.label || action}</span>
        </div>
        <button style={closeButtonStyles} onClick={onClose} title="Close">
          ✕
        </button>
      </div>

      {/* Content */}
      <div style={contentStyles}>
        {/* Step Info */}
        <div style={sectionStyles}>
          <div style={sectionTitleStyles}>Step Info</div>
          <div style={fieldGroupStyles}>
            <label style={labelStyles}>Step Name</label>
            <input
              type="text"
              value={localName}
              style={inputStyles}
              onChange={(e) => setLocalName(e.target.value)}
            />
          </div>
          <div style={fieldGroupStyles}>
            <label style={labelStyles}>Step ID</label>
            <input type="text" value={stepId} style={inputStyles} disabled />
          </div>
        </div>

        {/* Condition */}
        <div style={sectionStyles}>
          <div style={sectionTitleStyles}>Condition (Optional)</div>
          <textarea
            value={localCondition}
            placeholder="{{ params.some_value == true }}"
            style={textareaStyles}
            onChange={(e) => setLocalCondition(e.target.value)}
          />
          <div style={helpTextStyles}>
            Jinja2 expression. Step runs only if condition evaluates to true.
          </div>
        </div>

        {/* Ungrouped Parameters */}
        {groupedParams.ungrouped.length > 0 && (
          <div style={sectionStyles}>
            <div style={sectionTitleStyles}>Parameters</div>
            {groupedParams.ungrouped.map(renderField)}
          </div>
        )}

        {/* Grouped Parameters */}
        {Object.entries(groupedParams.groups).map(([groupName, params]) => (
          <div key={groupName} style={sectionStyles}>
            <div style={sectionTitleStyles}>{groupName}</div>
            {params.map(renderField)}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={footerStyles}>
        {onDelete && (
          <button
            style={dangerButtonStyles}
            onClick={onDelete}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'rgba(255, 77, 79, 0.2)';
              e.currentTarget.style.borderColor = '#ff4d4f';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.borderColor = 'rgba(255, 77, 79, 0.25)';
            }}
          >
            Delete
          </button>
        )}
        <button
          style={{
            ...primaryButtonStyles,
            opacity: isSaving ? 0.7 : 1,
            cursor: isSaving ? 'not-allowed' : 'pointer',
          }}
          onClick={handleSave}
          disabled={isSaving}
          onMouseOver={(e) => {
            if (!isSaving) {
              e.currentTarget.style.background = '#7A4BC7';
              e.currentTarget.style.borderColor = '#7A4BC7';
            }
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = '#965CDE';
            e.currentTarget.style.borderColor = '#965CDE';
          }}
        >
          {isSaving ? 'Validating...' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default ActionConfigPanel;
