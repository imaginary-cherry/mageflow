/**
 * MageFlow Visualizer App
 *
 * Main entry point for the React application.
 */

import React from 'react';
import { WorkflowViewer } from './components';
import './App.css';

function App() {
  return (
    <div className="app">
      <WorkflowViewer />
    </div>
  );
}

export default App;
