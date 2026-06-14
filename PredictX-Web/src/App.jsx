import React from 'react';
import './index.css';
import Header from './components/layout/Header';
import HomeView from './views/HomeView';

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-200">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <HomeView />
      </main>
    </div>
  );
}

export default App;