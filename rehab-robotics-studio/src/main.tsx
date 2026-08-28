import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './styles/app.css';

// Application entry point. Keep global providers or one-time browser setup here;
// route actual UI behavior through App and the feature folders instead.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
