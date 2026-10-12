import { StrictMode } from 'react';
import * as React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import 'katex/dist/katex.min.css';
import './index.css';

if (import.meta.env.DEV) {
  (window as unknown as { __React?: typeof React; __createRoot?: typeof createRoot }).__React = React;
  (window as unknown as { __React?: typeof React; __createRoot?: typeof createRoot }).__createRoot = createRoot;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
