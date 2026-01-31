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
  onTraceReceived?: (trace: any) => void;
  onTraceBatchReceived?: (traces: any[]) => void;
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
  onTraceBatchReceived,
  onError,
}: UseObservabilitySocketProps): UseObservabilitySocketReturn {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  // Use refs to avoid re-creating socket on every render
  const socketRef = useRef<Socket | null>(null);
  const onTraceReceivedRef = useRef(onTraceReceived);
  const onTraceBatchReceivedRef = useRef(onTraceBatchReceived);
  const onErrorRef = useRef(onError);
  const isConnectingRef = useRef(false);

  // Update callback refs
  onTraceReceivedRef.current = onTraceReceived;
  onTraceBatchReceivedRef.current = onTraceBatchReceived;
  onErrorRef.current = onError;

  useEffect(() => {
    // Helper function to cleanup socket
    const cleanupSocket = () => {
      if (socketRef.current) {
        console.log('[ObservabilitySocket] Cleanup - disconnecting socket');
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      isConnectingRef.current = false;
    };

    // Skip if not enabled or missing required params
    if (!enabled || !projectId || !promptId) {
      cleanupSocket();
      setConnectionStatus('disconnected');
      setError(null);
      return cleanupSocket; // Always return cleanup
    }

    // Check socket URL
    if (!observabilitySocketUrl) {
      console.error('[ObservabilitySocket] Missing NEXT_PUBLIC_BUDNOTIFY_SERVICE_PUBLIC');
      setError(new Error('Socket URL not configured'));
      setConnectionStatus('error');
      return cleanupSocket; // Always return cleanup
    }

    // Get JWT token
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.error('[ObservabilitySocket] No authentication token');
      setError(new Error('No authentication token'));
      setConnectionStatus('error');
      return cleanupSocket; // Always return cleanup
    }

    // Disconnect any existing socket first (handles React StrictMode and re-renders)
    cleanupSocket();

    // Mark as connecting
    isConnectingRef.current = true;
    setConnectionStatus('connecting');
    setError(null);

    console.log('[ObservabilitySocket] Creating socket connection to:', observabilitySocketUrl);
    console.log('[ObservabilitySocket] Filters:', { project_id: projectId, prompt_id: promptId });

    // Create socket
    // Browser WebSocket connections cannot send custom HTTP headers.
    // We use Socket.IO 4.x 'auth' option which sends auth data during the handshake.
    // This works with websocket transport in browsers.
    const socket = io(observabilitySocketUrl, {
      path: '/ws/socket.io',
      // Use websocket directly - auth is handled via Socket.IO handshake, not HTTP headers
      transports: ['websocket'],
      // Socket.IO 4.x auth - sent during handshake (works with websocket in browsers)
      // Server reads from socket.handshake.auth
      auth: {
        token: token,
      },
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[ObservabilitySocket] Connected! Socket ID:', socket.id);
      setConnectionStatus('connected');
      isConnectingRef.current = false;

      // Subscribe immediately after connect
      const subscribePayload = {
        channel: 'observability',
        filters: {
          project_id: projectId,
          prompt_id: promptId,
        },
      };
      console.log('[ObservabilitySocket] Emitting subscribe with payload:', JSON.stringify(subscribePayload, null, 2));
      socket.emit('subscribe', subscribePayload);
    });

    socket.on('authenticated', (msg) => {
      console.log('[ObservabilitySocket] Authenticated:', msg);
    });

    socket.on('subscribed', (msg) => {
      console.log('[ObservabilitySocket] Subscribed successfully!', msg);
      console.log('[ObservabilitySocket] Now listening for data on channel: observability');
      setConnectionStatus('subscribed');
    });

    socket.on('data', (payload: any) => {
      console.log('[ObservabilitySocket] ====== RECEIVED TRACE DATA ======');
      console.log('[ObservabilitySocket] Payload:', payload);

      // Handle the data structure: { channel: "observability", data: TraceSpan[] }
      const traces = payload?.data || payload;

      if (Array.isArray(traces)) {
        console.log(`[ObservabilitySocket] Processing ${traces.length} traces`);
        // Prefer batch handler for array data (enables tree building)
        if (onTraceBatchReceivedRef.current) {
          onTraceBatchReceivedRef.current(traces);
        } else {
          // Fallback to individual processing
          traces.forEach((trace: any) => {
            onTraceReceivedRef.current?.(trace);
          });
        }
      } else if (traces && typeof traces === 'object') {
        // Single trace object
        onTraceReceivedRef.current?.(traces);
      }
    });

    socket.on('error', (err: any) => {
      console.error('[ObservabilitySocket] Error event:', err);
      const socketError = err instanceof Error ? err : new Error(String(err));
      setError(socketError);
      setConnectionStatus('error');
      isConnectingRef.current = false;
      onErrorRef.current?.(socketError);
    });

    socket.on('connect_error', (err: any) => {
      // Log detailed error information for debugging
      console.error('[ObservabilitySocket] Connection error:', err.message);
      console.error('[ObservabilitySocket] Error details:', {
        type: err.type,
        description: err.description,
        context: err.context,
        transport: socket.io?.engine?.transport?.name,
      });
      setError(err);
      setConnectionStatus('error');
      isConnectingRef.current = false;
      onErrorRef.current?.(err);
    });

    socket.on('disconnect', (reason) => {
      console.log('[ObservabilitySocket] Disconnected:', reason);
      // Only set disconnected if we haven't already cleaned up (prevents state updates after unmount)
      if (socketRef.current === socket) {
        setConnectionStatus('disconnected');
        isConnectingRef.current = false;
      }
    });

    // Cleanup function - always return this
    return () => {
      console.log('[ObservabilitySocket] Effect cleanup - disconnecting socket');
      socket.off('connect');
      socket.off('authenticated');
      socket.off('subscribed');
      socket.off('data');
      socket.off('error');
      socket.off('connect_error');
      socket.off('disconnect');
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
