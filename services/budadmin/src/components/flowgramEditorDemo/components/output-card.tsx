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
        background: 'transparent',
      }}>
        {outputVariables.map((variable: AgentVariable, index: number) => (
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
              {variable.name || `Output Variable ${index + 1}`}
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
        {outputVariables.length} output variable{outputVariables.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
};
