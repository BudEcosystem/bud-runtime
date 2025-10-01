import { Field } from '@flowgram.ai/fixed-layout-editor';
import { AgentVariable } from '@/stores/useAgentStore';
import { useSession } from '../contexts/SessionContext';

export const OutputCard = () => {
  const { session } = useSession();

  // Get output variables from the session, with default if empty
  const sessionVariables = session?.outputVariables || [];

  const outputVariables: AgentVariable[] = sessionVariables.length > 0 ? sessionVariables : [
    {
      id: 'default-output-1',
      name: 'Output Variable 1',
      value: '',
      type: 'output',
      description: '',
      dataType: 'string',
      defaultValue: ''
    }
  ];

  return (
    <div className="output-card" style={{
      background: 'white',
      borderRadius: '12px',
      padding: '20px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      minWidth: '320px',
      maxWidth: '400px',
    }}>
      {/* Card Header */}
      <div style={{
        borderBottom: '1px solid #e5e7eb',
        paddingBottom: '12px',
        marginBottom: '20px',
      }}>
        <Field<string> name="title">
          {() => (
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: '#1f2937',
              margin: 0,
            }}>
              {'Output'}
            </h3>
          )}
        </Field>
      </div>

      {/* Output Variables List */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
      }}>
        {outputVariables.map((variable: AgentVariable, index: number) => (
          <div key={variable.id} style={{
            padding: '12px',
            background: '#f9fafb',
            borderRadius: '8px',
            border: '1px solid #e5e7eb',
          }}>
            <div style={{
              fontSize: '14px',
              fontWeight: '500',
              color: '#374151',
              marginBottom: '4px',
            }}>
              {variable.name || `Output Variable ${index + 1}`}
            </div>
            {variable.description && (
              <div style={{
                fontSize: '12px',
                color: '#6b7280',
                marginBottom: '8px',
              }}>
                {variable.description}
              </div>
            )}
            <div style={{
              fontSize: '12px',
              color: '#9ca3af',
            }}>
              Type: {variable.dataType || 'string'}
            </div>
          </div>
        ))}
      </div>

      {/* Card Footer */}
      <div style={{
        paddingTop: '12px',
        borderTop: '1px solid #e5e7eb',
        fontSize: '12px',
        color: '#6b7280',
        textAlign: 'center',
      }}>
        {outputVariables.length} output variable{outputVariables.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
};
