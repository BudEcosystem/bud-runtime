"use client";

import NormalEditor from '@/app/components/bud/components/input/NormalEditor';

interface UnstructuredPromptInputProps {
  promptId: string;
  promptVersion?: string;
  deploymentName?: string;
  chatId: string;
  onSubmit: (data: any) => void;
  status: string;
  stop: () => void;
  input: string;
  handleInputChange: (e: any) => void;
  error?: Error;
  disabled?: boolean;
}

export default function UnstructuredPromptInput({
  promptId,
  promptVersion,
  deploymentName,
  onSubmit,
  status,
  stop,
  input,
  handleInputChange,
  error,
  disabled
}: UnstructuredPromptInputProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim()) return;

    // Create payload similar to PromptForm unstructured
    const payload: any = {
      prompt: {
        id: promptId,
      },
      promptId: promptId,
      input: input,
    };

    // Add version if available
    if (promptVersion !== undefined && promptVersion !== null) {
      payload.prompt.version = String(promptVersion);
    }

    // Add deployment name if available
    if (deploymentName && typeof deploymentName === 'string') {
      payload.model = deploymentName;
    }

    console.log('Unstructured prompt payload:', payload);

    // Call parent submit handler
    onSubmit(payload);
  };

  return (
    <>
      <NormalEditor
        isLoading={status === "submitted" || status === "streaming"}
        error={error}
        disabled={disabled}
        isPromptMode={true}
        stop={stop}
        handleInputChange={handleInputChange}
        handleSubmit={handleSubmit}
        input={input}
      />
      <span className="text-white text-[0.75rem] opacity-50 mt-1 mb-2">
        You are chatting using the unstructured prompt format.
      </span>
    </>
  );
}
