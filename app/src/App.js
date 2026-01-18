import React, { useState } from 'react';
import TaskWorkflow from './components/TaskWorkflow';
import ChainTaskWorkflow from './components/ChainTaskWorkflow';
import './App.css';
import styles from './App.module.css';

function App() {
  const [showChains, setShowChains] = useState(true);
  
  return (
    <div className={styles.app}>
      <div className={styles.toggleContainer}>
        <button 
          onClick={() => setShowChains(!showChains)}
          className={`${styles.toggleButton} ${showChains ? styles.toggleButtonChain : styles.toggleButtonRegular}`}
        >
          {showChains ? 'Show Regular Workflow' : 'Show Chain Workflow'}
        </button>
      </div>
      {showChains ? <ChainTaskWorkflow /> : <TaskWorkflow />}
    </div>
  );
}

export default App;