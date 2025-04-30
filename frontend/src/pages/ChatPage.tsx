import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Header } from '@/components/custom/Header';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage, ThinkingMessage } from '@/components/custom/ChatMessage';
import { Overview } from '@/components/custom/Overview';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal } from 'lucide-react';
import { useScrollToBottom } from '@/hooks/useScrollToBottom';
import { EnhancedMessage } from '@/interfaces/interfaces';

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL ?? 'ws://localhost:8000/ws';
const RECONNECT_DELAY = 5000;

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<EnhancedMessage[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatId, setChatId] = useState<string | null>(null);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number>();
  const [scrollRef, endRef] = useScrollToBottom(messages, isLoading);

  const connect = useCallback(() => {
    if (ws.current) return;
    const sock = new WebSocket(WS_URL);
    ws.current = sock;

    sock.onopen = () => {
      console.debug('WS open');
      setIsConnected(true);
      setError(null);
    };

    sock.onmessage = (evt) => {
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
    };

    sock.onerror = (e) => {
      console.error('WS error', e);
      setError('WebSocket error');
      setIsConnected(false);
      setIsLoading(false);
      ws.current?.close();
    };

    sock.onclose = (e) => {
      console.debug('WS closed', e);
      setIsConnected(false);
      setIsLoading(false);
      ws.current = null;
      if (!e.wasClean) {
        reconnectTimer.current = window.setTimeout(connect, RECONNECT_DELAY);
      }
    };
  }, []);

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

      const payload = { chat_id: chatId, message: text };
      ws.current.send(JSON.stringify(payload));
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
          <AlertDescription>{error}</AlertDescription>
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
      </div>
    </div>
  );
};

export default ChatPage;
