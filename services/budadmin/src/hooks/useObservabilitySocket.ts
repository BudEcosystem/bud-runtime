import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { observabilitySocketUrl } from '@/components/environment';

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'subscribed'
  | 'error';

interface UseObservabilitySocketProps {
  projectId: string;
  promptId: string;
  enabled: boolean;
  onTraceReceived: (trace: any) => void;
  onError?: (error: Error) => void;
}

interface UseObservabilitySocketReturn {
  isConnected: boolean;
  isSubscribed: boolean;
  connectionStatus: ConnectionStatus;
  error: Error | null;
}

/**
 * Custom hook for connecting to the observability Socket.IO server
 * and subscribing to real-time trace data.
 */
export function useObservabilitySocket({
  projectId,
  promptId,
  enabled,
  onTraceReceived,
  onError,
}: UseObservabilitySocketProps): UseObservabilitySocketReturn {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  // Use refs to avoid re-creating socket on every render
  const socketRef = useRef<Socket | null>(null);
  const onTraceReceivedRef = useRef(onTraceReceived);
  const onErrorRef = useRef(onError);
  const isConnectingRef = useRef(false);

  // Update callback refs
  onTraceReceivedRef.current = onTraceReceived;
  onErrorRef.current = onError;

  useEffect(() => {
    // Skip if not enabled or missing required params
    if (!enabled || !projectId || !promptId) {
      // Cleanup existing socket
      if (socketRef.current) {
        console.log('[ObservabilitySocket] Disabling - disconnecting socket');
        socketRef.current.disconnect();
        socketRef.current = null;
        isConnectingRef.current = false;
        setConnectionStatus('disconnected');
        setError(null);
      }
      return;
    }

    // Check socket URL
    if (!observabilitySocketUrl) {
      console.error('[ObservabilitySocket] Missing NEXT_PUBLIC_OBSERVABILITY_SOCKET_URL');
      setError(new Error('Socket URL not configured'));
      setConnectionStatus('error');
      return;
    }

    // Prevent multiple simultaneous connections (only if actively connecting)
    if (isConnectingRef.current) {
      console.log('[ObservabilitySocket] Already connecting, skipping');
      return;
    }

    // Get JWT token
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.error('[ObservabilitySocket] No authentication token');
      setError(new Error('No authentication token'));
      setConnectionStatus('error');
      return;
    }

    // Disconnect any existing socket first (handles React StrictMode)
    if (socketRef.current) {
      console.log('[ObservabilitySocket] Cleaning up existing socket before creating new one');
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    // Mark as connecting
    isConnectingRef.current = true;
    setConnectionStatus('connecting');
    setError(null);

    console.log('[ObservabilitySocket] Creating socket connection to:', observabilitySocketUrl);
    console.log('[ObservabilitySocket] Filters:', { project_id: projectId, prompt_id: promptId });

    // Create socket
    // Note: extraHeaders doesn't work with WebSockets in browsers
    // Use 'auth' option instead for JWT authentication
    const socket = io(observabilitySocketUrl, {
      path: '/ws/socket.io',
      transports: ['websocket', 'polling'], // Allow polling fallback
      auth: {
        token: token, // Server should read this from socket.handshake.auth.token
      },
      query: {
        token: token, // Fallback: some servers read from query params
      },
      reconnection: true,
      reconnectionAttempts: 3,
      reconnectionDelay: 2000,
      timeout: 10000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[ObservabilitySocket] Connected! Socket ID:', socket.id);
      setConnectionStatus('connected');
      isConnectingRef.current = false;

      // Subscribe immediately after connect
      console.log('[ObservabilitySocket] Emitting subscribe...');
      socket.emit('subscribe', {
        channel: 'observability',
        filters: {
          project_id: projectId,
          prompt_id: promptId,
        },
      });
    });

    socket.on('authenticated', (msg) => {
      console.log('[ObservabilitySocket] Authenticated:', msg);
    });

    socket.on('subscribed', (msg) => {
      console.log('[ObservabilitySocket] Subscribed!', msg);
      setConnectionStatus('subscribed');
    });

    socket.on('data', (data: any) => {
      console.log('[ObservabilitySocket] Received trace data:', data);
      onTraceReceivedRef.current?.(data);
    });

    socket.on('error', (err: any) => {
      console.error('[ObservabilitySocket] Error event:', err);
      const socketError = err instanceof Error ? err : new Error(String(err));
      setError(socketError);
      setConnectionStatus('error');
      isConnectingRef.current = false;
      onErrorRef.current?.(socketError);
    });

    socket.on('connect_error', (err) => {
      console.error('[ObservabilitySocket] Connection error:', err.message);
      setError(err);
      setConnectionStatus('error');
      isConnectingRef.current = false;
      onErrorRef.current?.(err);
    });

    socket.on('disconnect', (reason) => {
      console.log('[ObservabilitySocket] Disconnected:', reason);
      setConnectionStatus('disconnected');
      isConnectingRef.current = false;
    });

    // Cleanup function
    return () => {
      console.log('[ObservabilitySocket] Cleanup - disconnecting socket');
      socket.disconnect();
      socketRef.current = null;
      isConnectingRef.current = false;
    };
  }, [enabled, projectId, promptId]); // Only re-run when these change

  return {
    isConnected: connectionStatus === 'connected' || connectionStatus === 'subscribed',
    isSubscribed: connectionStatus === 'subscribed',
    connectionStatus,
    error,
  };
}
