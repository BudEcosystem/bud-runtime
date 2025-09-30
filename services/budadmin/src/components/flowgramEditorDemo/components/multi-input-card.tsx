import { useState } from 'react';
import { Field } from '@flowgram.ai/fixed-layout-editor';
import { nanoid } from 'nanoid';

interface InputField {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  type?: 'text' | 'number' | 'textarea' | 'select';
  options?: string[];
}

export const MultiInputCard = ({ node }: any) => {
  const [inputs, setInputs] = useState<InputField[]>([
    { id: nanoid(5), label: 'Name', value: '', placeholder: 'Enter name', type: 'text' },
    { id: nanoid(5), label: 'Email', value: '', placeholder: 'Enter email', type: 'text' },
    { id: nanoid(5), label: 'Age', value: '', placeholder: 'Enter age', type: 'number' },
    { id: nanoid(5), label: 'Description', value: '', placeholder: 'Enter description', type: 'textarea' },
  ]);

  const handleInputChange = (id: string, value: string) => {
    setInputs(prev =>
      prev.map(input =>
        input.id === id ? { ...input, value } : input
      )
    );
  };

  const addInput = () => {
    const newInput: InputField = {
      id: nanoid(5),
      label: `Input ${inputs.length + 1}`,
      value: '',
      placeholder: 'Enter value',
      type: 'text'
    };
    setInputs([...inputs, newInput]);
  };

  const removeInput = (id: string) => {
    if (inputs.length > 1) {
      setInputs(inputs.filter(input => input.id !== id));
    }
  };

  const renderInput = (input: InputField) => {
    switch (input.type) {
      case 'textarea':
        return (
          <textarea
            value={input.value}
            onChange={(e) => handleInputChange(input.id, e.target.value)}
            placeholder={input.placeholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows={3}
          />
        );
      case 'number':
        return (
          <input
            type="number"
            value={input.value}
            onChange={(e) => handleInputChange(input.id, e.target.value)}
            placeholder={input.placeholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        );
      case 'select':
        return (
          <select
            value={input.value}
            onChange={(e) => handleInputChange(input.id, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select an option</option>
            {input.options?.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        );
      default:
        return (
          <input
            type="text"
            value={input.value}
            onChange={(e) => handleInputChange(input.id, e.target.value)}
            placeholder={input.placeholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        );
    }
  };

  return (
    <div className="multi-input-card" style={{
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
          {({ field }) => (
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: '#1f2937',
              margin: 0,
            }}>
              {field.value || 'Multi-Input Form'}
            </h3>
          )}
        </Field>
      </div>

      {/* Input Fields */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        marginBottom: '20px',
      }}>
        {inputs.map((input, index) => (
          <div key={input.id} style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <label style={{
                fontSize: '14px',
                fontWeight: '500',
                color: '#374151',
              }}>
                {input.label}
              </label>
              {inputs.length > 1 && (
                <button
                  onClick={() => removeInput(input.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#ef4444',
                    cursor: 'pointer',
                    fontSize: '12px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    transition: 'background-color 0.2s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#fee2e2'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  Remove
                </button>
              )}
            </div>
            {renderInput(input)}
          </div>
        ))}
      </div>

      {/* Add Input Button */}
      <button
        onClick={addInput}
        style={{
          width: '100%',
          padding: '10px',
          background: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          fontSize: '14px',
          fontWeight: '500',
          cursor: 'pointer',
          transition: 'background-color 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2563eb'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#3b82f6'}
      >
        + Add Input Field
      </button>

      {/* Card Footer - Optional */}
      <div style={{
        marginTop: '20px',
        paddingTop: '12px',
        borderTop: '1px solid #e5e7eb',
        fontSize: '12px',
        color: '#6b7280',
      }}>
        {inputs.length} input field{inputs.length !== 1 ? 's' : ''} configured
      </div>
    </div>
  );
};
