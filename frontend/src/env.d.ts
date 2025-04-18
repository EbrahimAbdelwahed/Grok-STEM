/// <reference types="vite/client" />

declare global {
  interface ImportMetaEnv {
    readonly VITE_WEBSOCKET_URL?: string;
    // add other VITE_… vars here
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}