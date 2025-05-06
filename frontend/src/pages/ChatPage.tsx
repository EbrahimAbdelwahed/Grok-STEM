import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Header } from '@/components/custom/Header';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage, ThinkingMessage } from '@/components/custom/ChatMessage';
import { Overview } from '@/components/custom/Overview';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal, RefreshCw } from 'lucide-react';
import { useScrollToBottom } from '@/hooks/useScrollToBottom';
import { EnhancedMessage } from '@/interfaces/interfaces';
import { Button } from '@/components/ui/button';

// Get WebSocket URL dynamically based on environment
const getWebSocketUrl = () => {
  // First priority: Use the environment variable if available
  if (import.meta.env.VITE_WEBSOCKET_URL) {
    return import.meta.env.VITE_WEBSOCKET_URL;
  }
  
  // Second priority: If using ngrok or other non-localhost domain, derive WS URL from current host
  const isSecure = window.location.protocol === 'https:';
  const wsProtocol = isSecure ? 'wss://' : 'ws://';
  
  if (window.location.hostname !== 'localhost' && !window.location.hostname.includes('127.0.0.1')) {
    // For ngrok: Use the same hostname but with WebSocket protocol
    return `${wsProtocol}${window.location.host}/ws`;
  } 
  
  // Fallback to localhost
  return 'ws://localhost:8000/ws';
};

const RECONNECT_DELAY = 5000;
const MAX_RECONNECT_ATTEMPTS = 5;

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<EnhancedMessage[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatId, setChatId] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [showRetryButton, setShowRetryButton] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number>();
  const [scrollRef, endRef] = useScrollToBottom(messages, isLoading);

  const connect = useCallback(() => {
    if (ws.current) return;
    
    try {
      const currentWsUrl = getWebSocketUrl();
      console.log(`Connecting to WebSocket at: ${currentWsUrl} (Attempt: ${reconnectAttempts + 1})`);
      
      const sock = new WebSocket(currentWsUrl);
      ws.current = sock;

      sock.onopen = () => {
        console.debug('WS open');
        setIsConnected(true);
        setError(null);
        setReconnectAttempts(0);
        setShowRetryButton(false);
      };

      sock.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const { type, id, chat_id, content, steps, plotly_json } = msg as any;

          // capture initial chat_id
          if (type === 'init' && chat_id) {
            setChatId(chat_id);
            return;
          }

          if (type === 'text') {
            setMessages((m) => [...m, { id, role: 'assistant', text_content: content }]);
          } else if (type === 'steps') {
            setMessages((m) =>
              m.map((x) => (x.id === id ? { ...x, steps } : x))
            );
          } else if (type === 'plot') {
            setMessages((m) =>
              m.map((x) => (x.id === id ? { ...x, plotly_json } : x))
            );
          } else if (type === 'error') {
            setError(content);
          } else if (type === 'end') {
            setIsLoading(false);
          }
        } catch (parseError) {
          console.error('Error parsing WebSocket message:', parseError);
          setError('Failed to parse message from server');
        }
      };

      sock.onerror = (e) => {
        console.error('WS error', e);
        setError('WebSocket connection error. The server might be offline or unreachable.');
        setIsConnected(false);
        setIsLoading(false);
        ws.current?.close();
      };

      sock.onclose = (e) => {
        console.debug('WS closed', e.code, e.reason);
        setIsConnected(false);
        setIsLoading(false);
        ws.current = null;
        
        if (!e.wasClean) {
          const newAttemptCount = reconnectAttempts + 1;
          setReconnectAttempts(newAttemptCount);
          
          if (newAttemptCount < MAX_RECONNECT_ATTEMPTS) {
            console.log(`Scheduling reconnect attempt ${newAttemptCount + 1}/${MAX_RECONNECT_ATTEMPTS}`);
            reconnectTimer.current = window.setTimeout(connect, RECONNECT_DELAY);
          } else {
            console.log('Maximum reconnection attempts reached');
            setShowRetryButton(true);
            setError('Failed to connect after multiple attempts. The server might be offline.');
          }
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setError('Failed to establish WebSocket connection');
      setShowRetryButton(true);
    }
  }, [reconnectAttempts]);

  const handleRetryConnection = useCallback(() => {
    setReconnectAttempts(0);
    setShowRetryButton(false);
    setError(null);
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
    }
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);

  const handleSubmit = useCallback(
    (msgText?: string) => {
      const text = (msgText ?? input).trim();
      if (!text || !isConnected || !ws.current) return;
      setMessages((m) => [...m, { id: uuidv4(), role: 'user', text_content: text }]);
      setInput('');
      setIsLoading(true);
      setError(null);

      try {
        const payload = { chat_id: chatId, message: text };
        ws.current.send(JSON.stringify(payload));
      } catch (error) {
        console.error('Error sending message:', error);
        setError('Failed to send message');
        setIsLoading(false);
      }
    },
    [chatId, input, isConnected]
  );

  return (
    <div className="flex flex-col h-screen">
      <Header />
      {error && (
        <Alert variant="destructive" className="m-2">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="flex flex-col gap-2">
            <span>{error}</span>
            {showRetryButton && (
              <Button 
                variant="outline" 
                size="sm" 
                className="self-start" 
                onClick={handleRetryConnection}
              >
                <RefreshCw className="h-4 w-4 mr-2" /> Retry Connection
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      <ScrollArea className="flex-1" viewportRef={scrollRef}>
        <div className="p-4 space-y-4 max-w-3xl mx-auto">
          {messages.length === 0 && !isLoading && <Overview />}
          {messages.map((m) => (
            <ChatMessage key={m.id} message={m} scrollToStep={() => {}} />
          ))}
          {isLoading && <ThinkingMessage />}
          <div ref={endRef} />
        </div>
        <ScrollBar orientation="vertical" />
      </ScrollArea>

      <div className="p-4 border-t">
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={() => handleSubmit()}
          isLoading={isLoading}
          isConnected={isConnected}
        />
        {!isConnected && !error && (
          <p className="text-sm text-muted-foreground mt-2 text-center">
            Connecting to server... Please wait.
          </p>
        )}
      </div>
    </div>
  );
};

export default ChatPage;
