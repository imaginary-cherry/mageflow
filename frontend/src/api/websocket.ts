/**
 * WebSocket Client for Real-time Task Updates
 *
 * Features:
 * 1. Auto-reconnect with exponential backoff
 * 2. Message type handling
 * 3. Subscription management
 * 4. Heartbeat/ping-pong
 */

import { TaskStatus } from '../types';

// ============================================================================
// Configuration
// ============================================================================

const WS_BASE = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
const RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 30000;

// ============================================================================
// Types
// ============================================================================

export type MessageType =
  | 'task_status_changed'
  | 'task_updated'
  | 'subtask_added'
  | 'task_removed'
  | 'error';

export interface WSMessage {
  type: MessageType;
  taskId: string;
  payload?: Record<string, unknown>;
}

export interface TaskStatusChangedMessage extends WSMessage {
  type: 'task_status_changed';
  status: TaskStatus;
}

export interface TaskUpdatedMessage extends WSMessage {
  type: 'task_updated';
}

export interface SubtaskAddedMessage extends WSMessage {
  type: 'subtask_added';
  parentId: string;
}

export interface TaskRemovedMessage extends WSMessage {
  type: 'task_removed';
}

type MessageHandler = (message: WSMessage) => void;

// ============================================================================
// WebSocket Client Class
// ============================================================================

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private handlers = new Map<MessageType, Set<MessageHandler>>();
  private globalHandlers = new Set<MessageHandler>();
  private isIntentionallyClosed = false;

  constructor(url: string = WS_BASE) {
    this.url = url;
  }

  // ==========================================================================
  // Connection Management
  // ==========================================================================

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isIntentionallyClosed = false;

    try {
      this.ws = new WebSocket(this.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.clearTimers();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.debug('[WebSocket] Connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onclose = (event) => {
      console.debug('[WebSocket] Closed:', event.code, event.reason);
      this.clearTimers();

      if (!this.isIntentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage;
        this.handleMessage(message);
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    const delay = Math.min(
      RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY_MS
    );

    console.debug(`[WebSocket] Reconnecting in ${delay}ms...`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  // ==========================================================================
  // Message Handling
  // ==========================================================================

  private handleMessage(message: WSMessage): void {
    // Call type-specific handlers
    const typeHandlers = this.handlers.get(message.type);
    if (typeHandlers) {
      typeHandlers.forEach(handler => handler(message));
    }

    // Call global handlers
    this.globalHandlers.forEach(handler => handler(message));
  }

  // ==========================================================================
  // Subscription API
  // ==========================================================================

  subscribe(type: MessageType, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(type)?.delete(handler);
    };
  }

  subscribeAll(handler: MessageHandler): () => void {
    this.globalHandlers.add(handler);

    return () => {
      this.globalHandlers.delete(handler);
    };
  }

  // ==========================================================================
  // Send Messages
  // ==========================================================================

  send(message: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] Cannot send message: not connected');
    }
  }

  // Subscribe to specific task updates
  subscribeToTask(taskId: string): void {
    this.send({ type: 'subscribe', taskId });
  }

  unsubscribeFromTask(taskId: string): void {
    this.send({ type: 'unsubscribe', taskId });
  }

  // ==========================================================================
  // Status
  // ==========================================================================

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const wsClient = new WebSocketClient();

// ============================================================================
// React Hook for WebSocket
// ============================================================================

import { useEffect } from 'react';

export function useWebSocket(): WebSocketClient {
  useEffect(() => {
    wsClient.connect();
    return () => {
      // Don't disconnect on unmount - keep connection alive
    };
  }, []);

  return wsClient;
}

export function useWebSocketMessage(
  type: MessageType,
  handler: MessageHandler
): void {
  useEffect(() => {
    const unsubscribe = wsClient.subscribe(type, handler);
    return unsubscribe;
  }, [type, handler]);
}
