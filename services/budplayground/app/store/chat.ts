import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import { Note, Session, Settings } from '../types/chat';
import { Endpoint } from '../types/deployment';
import { SavedMessage } from '../types/chat';

interface ChatStore {
  activeChatList: Session[];
  setActiveChatList: (chatList: Session[]) => void;

  promptIds: string[];
  setPromptIds: (ids: string[]) => void;
  getPromptIds: () => string[];

  createChat: (chat: Session) => void;
  updateChat: (chat: Session) => void;
  getChat: (id: string) => Session | undefined;
  setDeployment: (chatId: string, deployment: Endpoint) => void;
  setDeploymentLock: (chatId: string, locked: boolean) => void;
  isDeploymentLocked: (chatId: string) => boolean;
  disableChat: (chatId: string) => void;
  enableChat: (chatId: string) => void;
  deleteChat: (chatId: string) => void;
  syncWithServer: () => Promise<void>;
  switchUser: () => void;

  // Session isolation functions
  clearPromptSessions: () => void;
  clearDefaultSessions: () => void;
  hasPromptSessions: () => boolean;
  hasDefaultSessions: () => boolean;

  messages: Record<string, SavedMessage[]>;
  addMessage: (chatId: string, message: SavedMessage) => void;
  getMessages: (chatId: string) => SavedMessage[];
  setMessages: (chatId: string, messages: SavedMessage[]) => void;
  deleteMessageAfter: (chatId: string, messageId: string) => void;

  setFeedback: (chatId: string, messageId: string, feedback: string) => void;
  getFeedback: (chatId: string, messageId: string) => string | undefined;

  settingPresets: Settings[];
  currentSettingPreset: Settings;
  setCurrentSettingPreset: (settings: Settings) => void;
  setSettingPresets: (settings: Settings[]) => void;
  addSettingPreset: (settings: Settings) => void;
  updateSettingPreset: (settings: Settings) => void;

  notes: Note[];
  setNotes: (notes: Note[]) => void;
  addNote: (note: Note) => void;
  updateNote: (note: Note) => void;
  deleteNote: (noteId: string) => void;
  getNotes: (chatId: string) => Note[];
}

// Generate user-specific storage key based on authentication method
const getUserIdentifier = (): string | null => {
  if (typeof window === 'undefined') return null;

  // For JWT/refresh token auth, get user_id from session data
  const isJWTAuth = localStorage.getItem('is_jwt_auth') === 'true';
  if (isJWTAuth) {
    const sessionData = localStorage.getItem('session_data');
    if (sessionData) {
      try {
        const parsed = JSON.parse(sessionData);
        return parsed.user_id;
      } catch (error) {
        console.error('Failed to parse session data:', error);
      }
    }
  }

  // For API key auth, use the API key itself as identifier
  const apiKey = localStorage.getItem('token') || localStorage.getItem('access_key');
  if (apiKey) {
    // Create a hash of the API key for privacy (simple approach)
    return btoa(apiKey).substring(0, 16); // Base64 encoded, first 16 chars
  }

  return null;
};

// Get a unique storage name with user identification
const getStorageName = () => {
  // Check if window is defined (client-side)
  if (typeof window !== 'undefined') {
    // Check for URL parameters first
    const urlParams = new URLSearchParams(window.location.search);
    const storageParam = urlParams.get('storage');

    if (storageParam) {
      return storageParam;
    }

    // Get user identifier
    const userIdentifier = getUserIdentifier();
    if (userIdentifier) {
      const baseStorage = process.env.NEXT_PUBLIC_STORAGE_NAME || 'chat-storage';
      return `${baseStorage}-${userIdentifier}`;
    }
  }

  // Check for environment variable (works on both server and client)
  const envStorage = process.env.NEXT_PUBLIC_STORAGE_NAME;

  // Use the env variable if available, otherwise fall back to default
  return envStorage || 'chat-storage';
};

// Track the current storage key to detect changes
let currentStorageKey: string | null = null;
let isStoreInitialized = false;
let isTransitioningUser = false; // Flag to prevent saves during user switch

// Custom persistence functions
const saveToStorage = (state: Partial<ChatStore>) => {
  if (typeof window === 'undefined') return;

  // Don't save during user transitions
  if (isTransitioningUser) {
    return;
  }

  const storageKey = getStorageName();

  // CRITICAL: Only prevent saves if we're truly switching between different authenticated users
  // Allow saves when:
  // 1. First time initialization (!currentStorageKey)
  // 2. Store hasn't been initialized yet (!isStoreInitialized)
  // 3. Same key (currentStorageKey === storageKey)
  // 4. Moving from anonymous to authenticated (currentStorageKey === 'chat-storage')

  if (currentStorageKey &&
      isStoreInitialized &&
      currentStorageKey !== storageKey &&
      currentStorageKey !== 'chat-storage' &&
      currentStorageKey !== `${process.env.NEXT_PUBLIC_STORAGE_NAME || 'chat-storage'}`) {
    console.warn(`PREVENTED: Attempted to save to different user's storage!`, {
      previousKey: currentStorageKey,
      newKey: storageKey,
      prevented: true
    });
    // Don't save - this would contaminate the new user's storage
    return;
  }

  currentStorageKey = storageKey;

  const dataToStore = {
    state: {
      activeChatList: state.activeChatList,
      messages: state.messages,
      settingPresets: state.settingPresets,
      currentSettingPreset: state.currentSettingPreset,
      notes: state.notes,
    },
    version: 0,
  };

  try {
    localStorage.setItem(storageKey, JSON.stringify(dataToStore));
  } catch (error) {
    console.error('Failed to save to storage:', error);
  }
};

const loadFromStorage = (): Partial<ChatStore> | null => {
  if (typeof window === 'undefined') return null;

  const storageKey = getStorageName();
  currentStorageKey = storageKey; // Update tracked key when loading

  try {
    const storedData = localStorage.getItem(storageKey);
    if (storedData) {
      const parsed = JSON.parse(storedData);
      return parsed.state || null;
    }
  } catch (error) {
    console.error('Failed to load from storage:', error);
  }

  return null;
};

// Helper function to clear sessions by a predicate (DRY principle)
const clearSessionsByPredicate = (
  state: Pick<ChatStore, 'activeChatList' | 'messages'>,
  shouldKeep: (chat: Session) => boolean,
): Pick<ChatStore, 'activeChatList' | 'messages'> => {
  const sessionsToKeep = state.activeChatList.filter(shouldKeep);
  const sessionsToRemove = state.activeChatList.filter(chat => !shouldKeep(chat));
  const idsToRemove = sessionsToRemove.map(chat => chat.id);

  const cleanedMessages = { ...state.messages };
  idsToRemove.forEach((id) => delete cleanedMessages[id]);

  return {
    activeChatList: sessionsToKeep,
    messages: cleanedMessages,
  };
};

// Create the store with custom persistence
export const useChatStore = create<ChatStore>()(
  subscribeWithSelector((set, get) => {
    // Delay initial load to prevent loading wrong user's data
    // The useUserSwitching hook will handle proper initialization
    // Don't load initially - let useUserSwitching handle it
    const initialState = null;

    const store = {
      activeChatList: [],  // Start empty, will be loaded by initializeStore
      setActiveChatList: (chatList: Session[]) => {
        set({ activeChatList: chatList });
        saveToStorage(get());
        get().syncWithServer();
      },

      promptIds: [],
      setPromptIds: (ids: string[]) => {
        set({ promptIds: ids });
      },
      getPromptIds: () => {
        return get().promptIds;
      },

      getChat: (id: string): Session | undefined => {
        return get().activeChatList.find((chat: Session) => chat.id === id);
      },

      setDeployment: (chatId: string, deployment: Endpoint) => {
        set((state) => ({
          activeChatList: state.activeChatList.map((chat: Session) =>
            chat.id === chatId ? { ...chat, selectedDeployment: deployment as unknown as Endpoint } : chat
          )
        }));
        saveToStorage(get());
      },

      setDeploymentLock: (chatId: string, locked: boolean) => {
        set((state) => ({
          activeChatList: state.activeChatList.map((chat: Session) =>
            chat.id === chatId ? { ...chat, deploymentLocked: locked } : chat
          )
        }));
        saveToStorage(get());
      },

      isDeploymentLocked: (chatId: string) => {
        const chat = get().activeChatList.find((c: Session) => c.id === chatId);
        return chat?.deploymentLocked ?? false;
      },

      createChat: (chat: Session) => {
        set((state) => ({
          activeChatList: [...(state.activeChatList || []), chat]
        }));
        saveToStorage(get());
        get().syncWithServer();
      },

      updateChat: (chat: Session) => {
        set((state) => ({
          activeChatList: state.activeChatList.map((c: Session) =>
            c.id === chat.id ? chat : c
          )
        }));
        saveToStorage(get());
      },

      deleteChat: (chatId: string) => {
        set((state) => {
          const updatedChatList = state.activeChatList.filter((chat: Session) => chat.id !== chatId);
          if (updatedChatList.length > 0) {
            updatedChatList[0].active = true;
          }
          return { activeChatList: updatedChatList };
        });
        saveToStorage(get());
      },

      disableChat: (chatId: string) => {
        set((state) => ({
          activeChatList: state.activeChatList.map((chat: Session) =>
            chat.id === chatId ? { ...chat, active: false } : chat
          )
        }));
        saveToStorage(get());
      },

      enableChat: (chatId: string) => {
        set((state) => ({
          activeChatList: state.activeChatList.map((chat: Session) =>
            chat.id === chatId ? { ...chat, active: true } : chat
          )
        }));
        saveToStorage(get());
      },

      syncWithServer: async () => {
        // Check if user is signed in (you'll need to implement this check)
        const isSignedIn = false; // Replace with actual auth check

        if (isSignedIn) {
          try {
            const chats = get().activeChatList;
            // Make API call to sync chats (implement your API endpoint)
            await fetch('/api/chats/sync', {
              method: 'POST',
              body: JSON.stringify({ chats }),
            });
          } catch (error) {
            console.error('Failed to sync chats with server:', error);
          }
        }
      },

      switchUser: () => {
        // Clear current state when user changes
        set({
          activeChatList: [],
          messages: {},
          settingPresets: [],
          currentSettingPreset: {} as Settings,
          notes: [],
        });

        // Load new user's data
        const newUserData = loadFromStorage();
        if (newUserData) {
          set(newUserData);
        }
      },

      // Clear prompt sessions - used when switching to default mode
      // Detects prompt sessions by isPromptSession flag OR legacy 'prompt_' prefix
      clearPromptSessions: () => {
        set((state) => {
          const isPrompt = (chat: Session) =>
            chat.isPromptSession === true || chat.id.startsWith('prompt_');
          const clearedState = clearSessionsByPredicate(state, (chat) => !isPrompt(chat));
          return {
            ...clearedState,
            promptIds: [], // Also clear promptIds
          };
        });
        saveToStorage(get());
      },

      // Clear default sessions (non-prompt) - used when switching to prompt mode
      clearDefaultSessions: () => {
        set((state) => {
          const isPrompt = (chat: Session) =>
            chat.isPromptSession === true || chat.id.startsWith('prompt_');
          return clearSessionsByPredicate(state, (chat) => isPrompt(chat));
        });
        saveToStorage(get());
      },

      // Check if there are any prompt sessions
      hasPromptSessions: () => {
        return get().activeChatList.some(
          (chat) => chat.isPromptSession === true || chat.id.startsWith('prompt_')
        );
      },

      // Check if there are any default sessions
      hasDefaultSessions: () => {
        return get().activeChatList.some(
          (chat) => chat.isPromptSession !== true && !chat.id.startsWith('prompt_')
        );
      },

      messages: {},  // Start empty, will be loaded by initializeStore

      addMessage: (chatId: string, message: SavedMessage) => {
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: [...(state.messages[chatId] || []), message]
          }
        }));
        saveToStorage(get());
      },

      getMessages: (chatId: string) => {
        return get().messages[chatId] || [];
      },

      setMessages: (chatId: string, messages: SavedMessage[]) => {
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: messages
          }
        }));
        saveToStorage(get());
      },

      deleteMessageAfter: (chatId: string, messageId: string) => {
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: state.messages[chatId].filter((message: SavedMessage, index, arr) => {
              const messageIndex = arr.findIndex((msg) => msg.id === messageId);
              return index <= messageIndex - 1;
            })
          }
        }));
        saveToStorage(get());
      },

      setFeedback: (chatId: string, messageId: string, feedback: string) => {
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: state.messages[chatId].map((message: SavedMessage) =>
              message.id === messageId ? { ...message, feedback: feedback } : message
            )
          }
        }));
        saveToStorage(get());
      },

      getFeedback: (chatId: string, messageId: string) => {
        const chatMessages = get().messages[chatId];
        if (!chatMessages) {
          return undefined;
        }
        return chatMessages.find((message: SavedMessage) => message.id === messageId)?.feedback;
      },

      settingPresets: [],  // Start empty, will be loaded by initializeStore
      setSettingPresets: (settings: Settings[]) => {
        set({ settingPresets: settings });
        saveToStorage(get());
      },

      currentSettingPreset: {} as Settings,  // Start empty, will be loaded by initializeStore

      setCurrentSettingPreset: (settings: Settings) => {
        set({ currentSettingPreset: settings });
        saveToStorage(get());
      },

      addSettingPreset: (settings: Settings) => {
        set((state) => ({
          settingPresets: [...(state.settingPresets || []), settings]
        }));
        saveToStorage(get());
      },

      updateSettingPreset: (settings: Settings) => {
        set((state) => ({
          settingPresets: state.settingPresets.map((preset: Settings) =>
            preset.id === settings.id ? settings : preset
          )
        }));
        saveToStorage(get());
      },

      notes: [],  // Start empty, will be loaded by initializeStore
      setNotes: (notes: Note[]) => {
        set({ notes });
        saveToStorage(get());
      },

      addNote: (note: Note) => {
        set((state) => ({
          notes: [...(state.notes || []), note]
        }));
        saveToStorage(get());
      },

      updateNote: (note: Note) => {
        set((state) => ({
          notes: state.notes.map((n: Note) =>
            n.id === note.id ? note : n
          )
        }));
        saveToStorage(get());
      },

      deleteNote: (noteId: string) => {
        set((state) => ({
          notes: state.notes.filter((n: Note) => n.id !== noteId)
        }));
        saveToStorage(get());
      },

      getNotes: (chatId: string) => {
        return get().notes.filter((n: Note) => n.chat_session_id === chatId);
      },
    };

    return store;
  })
);

// Export helper function to reload store when user changes
export const reloadStoreForUser = () => {
  const newStorageKey = getStorageName();

  // Set transition flag to prevent saves during switch
  isTransitioningUser = true;

  // CRITICAL: Clear the store FIRST to prevent old data contamination
  useChatStore.setState({
    activeChatList: [],
    messages: {},
    settingPresets: [],
    currentSettingPreset: {} as Settings,
    notes: [],
  });

  // Update the tracked storage key BEFORE loading and mark as initialized
  currentStorageKey = newStorageKey;
  isStoreInitialized = true;

  // Now load the new user's data into the cleared store
  const newUserData = loadFromStorage();
  if (newUserData) {
    useChatStore.setState(newUserData);
  }

  // Clear transition flag after a short delay
  setTimeout(() => {
    isTransitioningUser = false;
  }, 500);
};

// Initialize store data on first load
export const initializeStore = () => {
  const storageKey = getStorageName();

  // CRITICAL: Clear any existing state first
  useChatStore.setState({
    activeChatList: [],
    messages: {},
    settingPresets: [],
    currentSettingPreset: {} as Settings,
    notes: [],
  });

  // Set the initial storage key and mark as initialized
  currentStorageKey = storageKey;
  isStoreInitialized = true;

  const userData = loadFromStorage();
  if (userData) {
    useChatStore.setState(userData);
  }
};
