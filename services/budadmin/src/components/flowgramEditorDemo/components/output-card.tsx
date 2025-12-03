import { Field } from '@flowgram.ai/fixed-layout-editor';
import { AgentVariable } from '@/stores/useAgentStore';
import { useSession } from '../contexts/SessionContext';
import { LoadingOutlined, CheckCircleFilled } from '@ant-design/icons';
import { Image} from "antd";

export const OutputCard = () => {
  const { session, outputWorkflowStatus, onDeleteVariable, structuredOutputEnabled } = useSession();

  // Get output variables from the session
  const sessionVariables = session?.outputVariables || [];

  // Show variables when structured output is enabled and there are variables
  const showVariables = structuredOutputEnabled && sessionVariables.length > 0;
  const outputVariables: AgentVariable[] = sessionVariables;

  return (
    <div className="output-card" style={{
      background: '#0E0E0E',
      borderRadius: '12px',
      padding: '20px',
      border: '1px solid #333333',
      minWidth: '320px',
      maxWidth: '400px',
      position: 'relative',
    }}>
      {/* Workflow Status Indicator - Top Right */}
      {outputWorkflowStatus && outputWorkflowStatus !== 'idle' && (
        <div style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 10,
        }}>
          {outputWorkflowStatus === 'loading' && (
            <LoadingOutlined
              style={{
                fontSize: '16px',
                color: '#965CDE',
                animation: 'spin 1s linear infinite',
              }}
              spin
            />
          )}
          {outputWorkflowStatus === 'success' && (
            <CheckCircleFilled
              style={{
                fontSize: '16px',
                color: '#52C41A',
              }}
            />
          )}
          {outputWorkflowStatus === 'failed' && (
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              style={{
                color: '#FF4D4F',
              }}
            >
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="2" fill="none" />
              <path d="M5 5L11 11M11 5L5 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          )}
        </div>
      )}
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
        {showVariables ? (
          outputVariables.map((variable: AgentVariable, index: number) => (
            <div key={variable.id} style={{
              padding: '.8rem',
              borderRadius: '.75rem',
              background: '#FFFFFF05',
            }}
            className='group flex justify-between items-center cursor-default'
            >
              <div style={{
                fontSize: '12px',
                color: '#EEEEEE',
                marginBottom: '4px',
                background: 'transparent',
              }}>
                {variable.name || `Output Variable ${index + 1}`}
              </div>

              {outputVariables.length > 1 && index > 0 && (
                <div
                  className='opacity-0 group-hover:opacity-100 cursor-pointer'
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteVariable?.(variable.id);
                  }}
                >
                  <Image
                    preview={false}
                    width={'0.8125rem'}
                    height={'0.8125rem'}
                    alt='delete'
                    src="/icons/deleteWhite.svg"
                  />
                </div>
              )}
            </div>
          ))
        ) : (
          <div style={{
            padding: '.8rem',
            borderRadius: '.75rem',
            background: '#FFFFFF05',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: '12px',
              color: '#808080',
            }}>
              Click to add a variable
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
