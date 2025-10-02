import { Field } from '@flowgram.ai/fixed-layout-editor';
import { useSession } from '../contexts/SessionContext';

export const PromptMessagesCard = () => {
  const { session } = useSession();

  // Get prompt messages from the session, with default if empty
  const promptMessages = session?.promptMessages || '';

  return (
    <div className="prompt-messages-card" style={{
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
            color: promptMessages ? '#EEEEEE' : '#808080',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: 'transparent',
          }}>
            {promptMessages || 'Enter prompt messages'}
          </div>
        </div>
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
        {promptMessages ? 'Prompt messages configured' : 'No prompt messages set'}
      </div>
    </div>
  );
};
