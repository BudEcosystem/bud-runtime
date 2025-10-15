import { Field } from '@flowgram.ai/fixed-layout-editor';
import { useSession } from '../contexts/SessionContext';
import { LoadingOutlined, CheckCircleFilled } from '@ant-design/icons';

export const PromptMessagesCard = () => {
  const { session, promptMessagesWorkflowStatus } = useSession();

  // Get prompt messages from the session, with default if empty
  const promptMessages = session?.promptMessages || '';

  // Parse and format the messages for display
  const getDisplayContent = () => {
    if (!promptMessages) {
      return 'Enter prompt messages';
    }

    try {
      const parsed = JSON.parse(promptMessages);
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Display all message contents, one per line
        return parsed.map((msg: any) => msg.content || '').filter(Boolean).join('\n\n');
      }
      return promptMessages;
    } catch (e) {
      // If it's not valid JSON, display as-is
      return promptMessages;
    }
  };

  // Get count of messages for footer
  const getMessageCount = () => {
    if (!promptMessages) return 0;
    try {
      const parsed = JSON.parse(promptMessages);
      if (Array.isArray(parsed)) {
        return parsed.length;
      }
      return 1;
    } catch (e) {
      return promptMessages ? 1 : 0;
    }
  };

  const displayContent = getDisplayContent();
  const messageCount = getMessageCount();

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
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="2" fill="none"/>
              <path d="M5 5L11 11M11 5L5 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
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
        <div style={{
          padding: '12px',
          borderRadius: '8px',
          minHeight: '80px',
          background: '#FFFFFF05',
        }}>
          <div style={{
            fontSize: '12px',
            color: displayContent === 'Enter prompt messages' ? '#808080' : '#EEEEEE',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: 'transparent',
          }}>
            {displayContent}
          </div>
        </div>
      </div>
    </div>
  );
};
