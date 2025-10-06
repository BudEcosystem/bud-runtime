import { Field } from '@flowgram.ai/fixed-layout-editor';
import { AgentVariable } from '@/stores/useAgentStore';
import { useSession } from '../contexts/SessionContext';
import { PrimaryButton } from '../../ui/bud/form/Buttons';

export const MultiInputCard = () => {
  const { session, onSavePromptSchema, isSaving } = useSession();

  // Get input variables from the session, with default if empty
  const sessionVariables = session?.inputVariables || [];

  const inputVariables: AgentVariable[] = sessionVariables.length > 0 ? sessionVariables : [
    {
      id: 'default-1',
      name: 'Input Variable 1',
      value: '',
      type: 'input',
      description: '',
      dataType: 'string',
      defaultValue: ''
    }
  ];

  return (
    <div className="multi-input-card" style={{
      background: '#0E0E0E',
      borderRadius: '12px',
      padding: '20px',
      border: '1px solid #333333',
      minWidth: '320px',
      maxWidth: '400px',
    }}>
      {/* Card Header */}
      <div style={{
        borderBottom: '1px solid #333333',
        paddingBottom: '12px',
        marginBottom: '20px',
        background: 'transparent',
      }}>
        <Field<string> name="title">
          {() => (
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: '#EEEEEE',
              margin: 0,
              background: 'transparent',
            }}>
              {'Input'}
            </h3>
          )}
        </Field>
      </div>

      {/* Input Variables List */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
        background: 'transparent',
      }}>
        {inputVariables.map((variable: AgentVariable, index: number) => (
          <div key={variable.id} style={{
            padding: '12px',
            borderRadius: '8px',
            background: '#FFFFFF05',
          }}>
            <div style={{
              fontSize: '12px',
              color: '#EEEEEE',
              marginBottom: '4px',
              background: 'transparent',
            }}>
              {variable.name || `Input Variable ${index + 1}`}
            </div>
            {variable.description && (
              <div style={{
                fontSize: '11px',
                color: '#B3B3B3',
                marginBottom: '8px',
                background: 'transparent',
              }}>
                {variable.description}
              </div>
            )}
            <div style={{
              fontSize: '11px',
              color: '#808080',
              background: 'transparent',
            }}>
              Type: {variable.dataType || 'string'}
            </div>
          </div>
        ))}
      </div>

      {/* Card Footer */}
      <div style={{
        paddingTop: '12px',
        borderTop: 'none',
        fontSize: '12px',
        color: '#808080',
        textAlign: 'center',
        background: 'transparent',
      }}>
        {inputVariables.length} input variable{inputVariables.length !== 1 ? 's' : ''}
      </div>

      {/* Save Button */}
      {onSavePromptSchema && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid #333333',
          background: 'transparent',
        }}>
          <PrimaryButton
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation();
              onSavePromptSchema();
            }}
            loading={isSaving}
            disabled={isSaving}
            style={{
              background: '#965CDE',
              border: 'none',
              color: 'white',
              padding: '8px 24px',
              borderRadius: '8px',
              fontSize: '14px',
              cursor: isSaving ? 'not-allowed' : 'pointer',
            }}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </PrimaryButton>
        </div>
      )}
    </div>
  );
};
