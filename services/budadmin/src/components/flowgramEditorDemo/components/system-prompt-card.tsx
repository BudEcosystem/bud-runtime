import { Field } from '@flowgram.ai/fixed-layout-editor';
import { useSession } from '../contexts/SessionContext';

export const SystemPromptCard = () => {
  const { session } = useSession();

  // Get system prompt from the session, with default if empty
  const systemPrompt = session?.systemPrompt || '';

  return (
    <div className="system-prompt-card" style={{
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
      }}>
        <div style={{
          padding: '12px',
          background: '#f9fafb',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          minHeight: '80px',
        }}>
          <div style={{
            fontSize: '14px',
            color: systemPrompt ? '#374151' : '#9ca3af',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {systemPrompt || 'Enter system prompt'}
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div style={{
        paddingTop: '12px',
        borderTop: '1px solid #e5e7eb',
        fontSize: '12px',
        color: '#6b7280',
        textAlign: 'center',
      }}>
        {systemPrompt ? 'System prompt configured' : 'No system prompt set'}
      </div>
    </div>
  );
};
