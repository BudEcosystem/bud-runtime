'use client';

import React from 'react';
import { Input, Tooltip } from 'antd';
import { CredentialSchemaField } from '@/stores/useConnectors';
import { Text_12_400_EEEEEE } from '@/components/ui/text';
import { PrimaryButton } from '@/components/ui/bud/form/Buttons';
import CustomSelect from 'src/flows/components/CustomSelect';

// Helper to identify redirect URI fields - check both field name and common patterns
const REDIRECT_URI_FIELDS = ['redirect_uri', 'redirect_url', 'callback_url', 'redirecturi', 'redirecturl', 'callbackurl'];
const isRedirectUriField = (fieldName: string, label?: string) => {
  const normalizedField = fieldName.toLowerCase().replace(/[_-]/g, '');
  const normalizedLabel = label?.toLowerCase().replace(/[_-]/g, '') || '';

  // Check if field name matches any known patterns
  const fieldMatches = REDIRECT_URI_FIELDS.some(f => normalizedField.includes(f.replace(/[_-]/g, '')));
  // Check if label contains "redirect" and "uri" or "url"
  const labelMatches = (normalizedLabel.includes('redirect') && (normalizedLabel.includes('uri') || normalizedLabel.includes('url')));

  return fieldMatches || labelMatches;
};

interface CredentialConfigStepProps {
  credentialSchema: CredentialSchemaField[];
  formData: Record<string, string>;
  onInputChange: (field: string, value: string) => void;
  onContinue: () => void;
  isRegistering: boolean;
  isValid: boolean;
}

export const CredentialConfigStep: React.FC<CredentialConfigStepProps> = ({
  credentialSchema,
  formData,
  onInputChange,
  onContinue,
  isRegistering,
  isValid,
}) => {
  // Handler for copying redirect URI to clipboard
  const handleCopyUri = async (fieldName: string) => {
    const value = formData[fieldName];
    if (value) {
      try {
        await navigator.clipboard.writeText(value);
      } catch (error) {
        console.error('Failed to copy URI:', error);
      }
    }
  };

  // Helper function to filter visible fields based on grant_type selection
  const getVisibleFields = (fields: CredentialSchemaField[]): CredentialSchemaField[] => {
    const grantTypeValue = formData['grant_type'];

    return fields.filter(field => {
      // If no visible_when, field is always visible
      if (!field.visible_when || field.visible_when.length === 0) {
        return true;
      }
      // If visible_when exists, check if current grant_type is in the array
      return grantTypeValue && field.visible_when.includes(grantTypeValue);
    });
  };

  const renderFormField = (field: CredentialSchemaField) => {
    const inputClassName = "!bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3A3A3A] focus:border-[#965CDE] text-[#EEEEEE] text-[0.6875rem] font-[400] placeholder:text-[#808080] rounded-[.5rem] h-[1.9375rem]";
    const inputStyle = {
      backgroundColor: '#1A1A1A',
      borderColor: '#2A2A2A',
      color: 'white',
    };

    const renderLabel = () => (
      <Text_12_400_EEEEEE className="mb-1 block">
        {field.label}
        {field.required && <span className="text-[#E82E2E] ml-0.5">*</span>}
      </Text_12_400_EEEEEE>
    );

    switch (field.type) {
      case 'dropdown':
        return (
          <div key={field.field}>
            {renderLabel()}
            <CustomSelect
              name={field.field}
              placeholder={field.label}
              value={formData[field.field]}
              onChange={(value) => onInputChange(field.field, value)}
              selectOptions={field.options?.map(opt => ({ label: opt.replace(/_/g, ' '), value: opt }))}
              InputClasses="!h-[1.9375rem] min-h-[1.9375rem] !text-[0.6875rem] !py-[.45rem]"
            />
          </div>
        );

      case 'password':
        return (
          <div key={field.field}>
            {renderLabel()}
            <Input
              type="password"
              placeholder={field.label}
              value={formData[field.field] || ''}
              onChange={(e) => onInputChange(field.field, e.target.value)}
              className={inputClassName}
              style={inputStyle}
              autoComplete="new-password"
            />
          </div>
        );

      case 'url':
      case 'text':
      default: {
        const isRedirectUri = isRedirectUriField(field.field, field.label);

        const copyButton = isRedirectUri ? (
          <Tooltip title="Copy Redirect URI" placement="top">
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleCopyUri(field.field);
              }}
              className="flex items-center justify-center hover:bg-[#2A2A2A] rounded transition-colors p-0.5"
              type="button"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-[#808080] hover:text-[#EEEEEE] transition-colors"
              >
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            </button>
          </Tooltip>
        ) : undefined;

        return (
          <div key={field.field}>
            {renderLabel()}
            <Input
              placeholder={field.label}
              value={formData[field.field] || ''}
              onChange={(e) => onInputChange(field.field, e.target.value)}
              className={inputClassName}
              style={{
                ...inputStyle,
                ...(isRedirectUri && {
                  cursor: 'not-allowed',
                  opacity: 0.7,
                }),
              }}
              autoComplete="off"
              disabled={isRedirectUri}
              suffix={copyButton}
            />
          </div>
        );
      }
    }
  };

  return (
    <div className='flex flex-col h-full justify-between'>
      {/* Dynamic Input Fields based on credential_schema */}
      <div className="space-y-3 mb-6 px-[1.125rem]">
        {getVisibleFields(credentialSchema)
          .sort((a, b) => a.order - b.order)
          .map(field => renderFormField(field))}
      </div>
      <div style={{
        marginTop: '18px',
        paddingTop: '18px',
        paddingBottom: '18px',
        borderRadius: '0 0 11px 11px',
        borderTop: '0.5px solid #1F1F1F',
        background: 'rgba(255, 255, 255, 0.03)',
        backdropFilter: 'blur(5px)'
      }} className='px-[1rem]'>
        <div className='flex justify-end items-center px-[1rem]'>
          <PrimaryButton
            onClick={onContinue}
            loading={isRegistering}
            disabled={isRegistering || !isValid}
            style={{
              cursor: (isRegistering || !isValid) ? 'not-allowed' : 'pointer',
              transform: 'none'
            }}
            classNames="h-[1.375rem] rounded-[0.375rem] "
            textClass="!text-[0.625rem] !font-[400]"
          >
            {isRegistering ? 'Registering...' : 'Continue'}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
};
