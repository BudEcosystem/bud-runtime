import { Field } from '@flowgram.ai/fixed-layout-editor';
import { useSession } from '../contexts/SessionContext';
import { LoadingOutlined, CheckCircleFilled } from '@ant-design/icons';

interface PromptMessage {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export const PromptMessagesCard = () => {
  const { session, promptMessagesWorkflowStatus } = useSession();

  // Get prompt messages from the session, with default if empty
  const promptMessagesString = session?.promptMessages || '';

  // Parse messages from JSON string
  const messages: PromptMessage[] = (() => {
    if (!promptMessagesString) {
      return [];
    }
    try {
      const parsed = JSON.parse(promptMessagesString);
      if (Array.isArray(parsed)) {
        return parsed;
      }
      return [];
    } catch (e) {
      return [];
    }
  })();

  // Get role display name with color
  const getRoleDisplay = (role: string) => {
    const roleMap = {
      'system': { name: 'System', color: '#965CDE' },
      'user': { name: 'User', color: '#52C41A' },
      'assistant': { name: 'Assistant', color: '#1890FF' }
    };
    return roleMap[role as keyof typeof roleMap] || { name: role, color: '#808080' };
  };

  return (
    <div className="prompt-messages-card" style={{
      background: '#0E0E0E',
      borderRadius: '12px',
      padding: '20px',
      border: '1px solid #333333',
      minWidth: '320px',
      maxWidth: '400px',
      position: 'relative',
    }}>
      {/* Workflow Status Indicator - Top Right */}
      {promptMessagesWorkflowStatus && promptMessagesWorkflowStatus !== 'idle' && (
        <div style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 10,
        }}>
          {promptMessagesWorkflowStatus === 'loading' && (
            <LoadingOutlined
              style={{
                fontSize: '16px',
                color: '#965CDE',
                animation: 'spin 1s linear infinite',
              }}
              spin
            />
          )}
          {promptMessagesWorkflowStatus === 'success' && (
            <CheckCircleFilled
              style={{
                fontSize: '16px',
                color: '#52C41A',
              }}
            />
          )}
          {promptMessagesWorkflowStatus === 'failed' && (
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
              {'Prompt Messages'}
            </h3>
          )}
        </Field>
      </div>

      {/* Prompt Messages Content */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        marginBottom: '20px',
        background: 'transparent',
      }}>
        {messages.length === 0 ? (
          <div style={{
            padding: '.8rem',
            borderRadius: '.75rem',
            background: '#FFFFFF05',
          }}>
            <div style={{
              fontSize: '12px',
              color: '#808080',
              background: 'transparent',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              textAlign: 'center',
            }}>
              Enter prompt messages
            </div>
          </div>
        ) : (
          messages.map((message) => {
            const roleDisplay = getRoleDisplay(message.role);
            return (
              <div
                key={message.id}
                style={{
                  padding: '.8rem',
                  borderRadius: '.75rem',
                  background: '#FFFFFF05',
                }}
                className='flex flex-col gap-2 cursor-default'
              >
                {/* Role tag */}
                <div className='flex justify-start items-center'>
                  <div
                    style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      color: roleDisplay.color,
                      background: `${roleDisplay.color}15`,
                      padding: '3px 8px',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {roleDisplay.name}
                  </div>
                </div>
                {/* Message content */}
                <div style={{
                  fontSize: '12px',
                  color: '#EEEEEE',
                  fontWeight: '400',
                  background: 'transparent',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  paddingLeft: '2px',
                }}>
                  {message.content || <span style={{ color: '#606060' }}>No content</span>}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
