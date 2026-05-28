/**
 * Vite entry point — mounts the React tree into #root.
 *
 * Wraps the App in StrictMode and BrowserRouter. No providers beyond
 * routing are needed: auth state lives in localStorage and is read on
 * demand by `useAuth.hook`.
 *
 * @module main
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
