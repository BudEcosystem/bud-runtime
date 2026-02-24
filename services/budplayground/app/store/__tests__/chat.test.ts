import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useChatStore } from '../chat';
import { Session } from '../../types/chat';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Helper to create a default (non-prompt) session
const createDefaultSession = (id?: string): Session => ({
  id: id || crypto.randomUUID(),
  name: 'New Chat',
  total_tokens: 0,
  created_at: new Date().toISOString(),
  modified_at: new Date().toISOString(),
  chat_setting_id: 'default',
  active: true,
});

// Helper to create a prompt session (with a raw prompt ID, NOT prefixed with 'prompt_')
const createPromptSession = (promptId: string): Session => ({
  id: promptId, // Raw prompt ID, like a UUID - this is how prompt sessions are created in page.tsx
  name: 'Prompt 1',
  total_tokens: 0,
  created_at: new Date().toISOString(),
  modified_at: new Date().toISOString(),
  chat_setting_id: 'default',
  active: true,
  isPromptSession: true,
});

// Helper to create a legacy prompt session (ID starts with 'prompt_')
const createLegacyPromptSession = (promptId: string): Session => ({
  id: `prompt_${promptId}`,
  name: 'Prompt 1',
  total_tokens: 0,
  created_at: new Date().toISOString(),
  modified_at: new Date().toISOString(),
  chat_setting_id: 'default',
  active: true,
});

describe('Chat Store - Session Isolation', () => {
  beforeEach(() => {
    // Reset the store to a clean state
    useChatStore.setState({
      activeChatList: [],
      messages: {},
      promptIds: [],
      settingPresets: [],
      currentSettingPreset: {} as any,
      notes: [],
    });
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('hasPromptSessions', () => {
    it('should return false when no sessions exist', () => {
      const { hasPromptSessions } = useChatStore.getState();
      expect(hasPromptSessions()).toBe(false);
    });

    it('should return false when only default sessions exist', () => {
      const defaultSession = createDefaultSession();
      useChatStore.setState({ activeChatList: [defaultSession] });

      const { hasPromptSessions } = useChatStore.getState();
      expect(hasPromptSessions()).toBe(false);
    });

    it('should return true when sessions with prompt_ prefix exist (legacy)', () => {
      const promptSession = createLegacyPromptSession('abc123');
      useChatStore.setState({ activeChatList: [promptSession] });

      const { hasPromptSessions } = useChatStore.getState();
      expect(hasPromptSessions()).toBe(true);
    });

    it('should return true when sessions with isPromptSession flag exist (raw prompt IDs)', () => {
      // This is the KEY test - prompt sessions created from URL promptIds
      // have raw IDs (UUIDs/alphanumeric) that don't start with 'prompt_'
      const promptSession = createPromptSession('39c5a1b2-dcd9-43e5-9562-52d7178f07c5');
      useChatStore.setState({ activeChatList: [promptSession] });

      const { hasPromptSessions } = useChatStore.getState();
      expect(hasPromptSessions()).toBe(true);
    });

    it('should return true when mixed sessions exist with at least one prompt session', () => {
      const defaultSession = createDefaultSession();
      const promptSession = createPromptSession('pmpt_structured');
      useChatStore.setState({ activeChatList: [defaultSession, promptSession] });

      const { hasPromptSessions } = useChatStore.getState();
      expect(hasPromptSessions()).toBe(true);
    });
  });

  describe('clearPromptSessions', () => {
    it('should remove sessions flagged as prompt sessions (isPromptSession)', () => {
      const defaultSession = createDefaultSession();
      const promptSession = createPromptSession('39c5a1b2-dcd9-43e5-9562-52d7178f07c5');

      useChatStore.setState({
        activeChatList: [defaultSession, promptSession],
        messages: {
          [defaultSession.id]: [{ id: '1', content: 'hello', role: 'user', createdAt: new Date(), feedback: '' }],
          [promptSession.id]: [{ id: '2', content: 'prompt msg', role: 'user', createdAt: new Date(), feedback: '' }],
        },
        promptIds: ['39c5a1b2-dcd9-43e5-9562-52d7178f07c5'],
      });

      const { clearPromptSessions } = useChatStore.getState();
      clearPromptSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(1);
      expect(state.activeChatList[0].id).toBe(defaultSession.id);
      expect(state.messages[promptSession.id]).toBeUndefined();
      expect(state.messages[defaultSession.id]).toHaveLength(1);
      expect(state.promptIds).toEqual([]);
    });

    it('should remove legacy prompt_ prefixed sessions', () => {
      const legacyPromptSession = createLegacyPromptSession('abc123');
      useChatStore.setState({
        activeChatList: [legacyPromptSession],
        messages: {
          [legacyPromptSession.id]: [{ id: '1', content: 'msg', role: 'user', createdAt: new Date(), feedback: '' }],
        },
      });

      const { clearPromptSessions } = useChatStore.getState();
      clearPromptSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(0);
      expect(state.messages[legacyPromptSession.id]).toBeUndefined();
    });

    it('should clear promptIds when clearing prompt sessions', () => {
      const promptSession = createPromptSession('prompt-id-1');
      useChatStore.setState({
        activeChatList: [promptSession],
        promptIds: ['prompt-id-1'],
      });

      const { clearPromptSessions } = useChatStore.getState();
      clearPromptSessions();

      expect(useChatStore.getState().promptIds).toEqual([]);
    });

    it('should handle multiple prompt sessions with different ID formats', () => {
      const defaultSession = createDefaultSession();
      const promptSession1 = createPromptSession('uuid-like-prompt-id');
      const promptSession2 = createPromptSession('another-prompt-id');
      const legacyPromptSession = createLegacyPromptSession('legacy-id');

      useChatStore.setState({
        activeChatList: [defaultSession, promptSession1, promptSession2, legacyPromptSession],
        messages: {
          [defaultSession.id]: [{ id: 'm1', content: 'default', role: 'user', createdAt: new Date(), feedback: '' }],
          [promptSession1.id]: [{ id: 'm2', content: 'prompt1', role: 'user', createdAt: new Date(), feedback: '' }],
          [promptSession2.id]: [{ id: 'm3', content: 'prompt2', role: 'user', createdAt: new Date(), feedback: '' }],
          [legacyPromptSession.id]: [{ id: 'm4', content: 'legacy', role: 'user', createdAt: new Date(), feedback: '' }],
        },
        promptIds: ['uuid-like-prompt-id', 'another-prompt-id'],
      });

      const { clearPromptSessions } = useChatStore.getState();
      clearPromptSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(1);
      expect(state.activeChatList[0].id).toBe(defaultSession.id);
      expect(Object.keys(state.messages)).toEqual([defaultSession.id]);
    });
  });

  describe('clearDefaultSessions', () => {
    it('should remove default sessions and keep prompt sessions', () => {
      const defaultSession = createDefaultSession();
      const promptSession = createPromptSession('my-prompt-id');

      useChatStore.setState({
        activeChatList: [defaultSession, promptSession],
        messages: {
          [defaultSession.id]: [{ id: '1', content: 'default msg', role: 'user', createdAt: new Date(), feedback: '' }],
          [promptSession.id]: [{ id: '2', content: 'prompt msg', role: 'user', createdAt: new Date(), feedback: '' }],
        },
      });

      const { clearDefaultSessions } = useChatStore.getState();
      clearDefaultSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(1);
      expect(state.activeChatList[0].id).toBe('my-prompt-id');
      expect(state.messages[defaultSession.id]).toBeUndefined();
      expect(state.messages[promptSession.id]).toHaveLength(1);
    });

    it('should keep legacy prompt_ prefixed sessions', () => {
      const defaultSession = createDefaultSession();
      const legacySession = createLegacyPromptSession('legacy');

      useChatStore.setState({
        activeChatList: [defaultSession, legacySession],
      });

      const { clearDefaultSessions } = useChatStore.getState();
      clearDefaultSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(1);
      expect(state.activeChatList[0].id).toBe(legacySession.id);
    });
  });

  describe('Mode transition: prompt mode -> default mode', () => {
    it('should clear all prompt data when transitioning from prompt to default mode', () => {
      // Simulate: user was in prompt mode with sessions and messages
      const promptSession1 = createPromptSession('prompt-abc');
      const promptSession2 = createPromptSession('prompt-def');

      useChatStore.setState({
        activeChatList: [promptSession1, promptSession2],
        messages: {
          'prompt-abc': [
            { id: 'm1', content: 'user input', role: 'user', createdAt: new Date(), feedback: '' },
            { id: 'm2', content: 'ai response', role: 'assistant', createdAt: new Date(), feedback: '' },
          ],
          'prompt-def': [
            { id: 'm3', content: 'another input', role: 'user', createdAt: new Date(), feedback: '' },
          ],
        },
        promptIds: ['prompt-abc', 'prompt-def'],
      });

      // Verify prompt sessions are detected
      expect(useChatStore.getState().hasPromptSessions()).toBe(true);

      // Clear prompt sessions (simulating default mode entry)
      useChatStore.getState().clearPromptSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(0);
      expect(state.messages).toEqual({});
      expect(state.promptIds).toEqual([]);
      expect(state.hasPromptSessions()).toBe(false);
    });

    it('should detect prompt sessions even when IDs look like UUIDs', () => {
      // This is the exact scenario from the bug: prompt IDs are UUIDs
      const promptId = '39c5a1b2-dcd9-43e5-9562-52d7178f07c5';
      const promptSession = createPromptSession(promptId);

      useChatStore.setState({
        activeChatList: [promptSession],
        messages: {
          [promptId]: [
            { id: 'm1', content: 'test', role: 'user', createdAt: new Date(), feedback: '' },
          ],
        },
        promptIds: [promptId],
      });

      // This must return true even though the ID doesn't start with 'prompt_'
      expect(useChatStore.getState().hasPromptSessions()).toBe(true);

      // Clear should remove the session
      useChatStore.getState().clearPromptSessions();

      const state = useChatStore.getState();
      expect(state.activeChatList).toHaveLength(0);
      expect(state.messages[promptId]).toBeUndefined();
    });
  });

  describe('setPromptIds', () => {
    it('should set prompt IDs', () => {
      const { setPromptIds, getPromptIds } = useChatStore.getState();
      setPromptIds(['id1', 'id2']);
      expect(getPromptIds()).toEqual(['id1', 'id2']);
    });

    it('should clear prompt IDs when set to empty array', () => {
      useChatStore.setState({ promptIds: ['id1'] });
      const { setPromptIds, getPromptIds } = useChatStore.getState();
      setPromptIds([]);
      expect(getPromptIds()).toEqual([]);
    });
  });
});
