import { Field } from '@flowgram.ai/fixed-layout-editor';
import { useSession } from '../contexts/SessionContext';
import { LoadingOutlined, CheckCircleFilled } from '@ant-design/icons';

export const SystemPromptCard = () => {
  const { session, systemPromptWorkflowStatus } = useSession();

  // Get system prompt from the session, with default if empty
  const systemPrompt = session?.systemPrompt || '';

  return (
    <div className="system-prompt-card" style={{
      background: '#0E0E0E',
      borderRadius: '12px',
      padding: '20px',
      border: '1px solid #333333',
      minWidth: '320px',
      maxWidth: '400px',
      position: 'relative',
    }}>
      {/* Workflow Status Indicator - Top Right */}
      {systemPromptWorkflowStatus && systemPromptWorkflowStatus !== 'idle' && (
        <div style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 10,
        }}>
          {systemPromptWorkflowStatus === 'loading' && (
            <LoadingOutlined
              style={{
                fontSize: '16px',
                color: '#965CDE',
                animation: 'spin 1s linear infinite',
              }}
              spin
            />
          )}
          {systemPromptWorkflowStatus === 'success' && (
            <CheckCircleFilled
              style={{
                fontSize: '16px',
                color: '#52C41A',
              }}
            />
          )}
          {systemPromptWorkflowStatus === 'failed' && (
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
              {'System Prompt'}
            </h3>
          )}
        </Field>
      </div>

      {/* System Prompt Content */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
        background: 'transparent',
      }}>
        <div style={{
          padding: '.8rem',
          borderRadius: '.75rem',
          background: '#FFFFFF05',
        }}>
          <div style={{
            fontSize: '12px',
            color: systemPrompt ? '#EEEEEE' : '#808080',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: 'transparent',
            textAlign: 'center'
          }}>
            {systemPrompt || 'Enter system prompt'}
          </div>
        </div>
      </div>
    </div>
  );
};
