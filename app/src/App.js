import React from 'react';
import TaskWorkflow from './components/TaskWorkflow';
import './App.css';
import styles from './App.module.css';

function App() {
  return (
    <div className={styles.app}>
      <TaskWorkflow />
    </div>
  );
}

export default App;
