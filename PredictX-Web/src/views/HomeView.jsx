import React, { useEffect, useState } from 'react';
import SpotlightCarousel from '../components/SpotlightCarousel';
import MatchCenterDashboard from './MatchCenterDashboard';

const HomeView = () => {
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTodayGames = async () => {
      try {
        setLoading(true);
        const today = new Date().toISOString().split('T')[0];
        const data = await fetchGamesByDate(today);
        setGames(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTodayGames();
  }, []);

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-pulse w-12 h-12 border-4 border-primary/50 border-t-primary rounded-full"></div>
        <p className="mt-4 text-muted-text">載入今日焦點賽事中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-500">
        <p className="mb-2">載入失敗: {error}</p>
        <button
          onClick={() => window.location.reload()}
          className="bg-primary hover:bg-primary/90 text-white font-medium py-2 px-4 rounded transition-colors"
        >
          重新載入
        </button>
      </div>
    );
  }

  return (
    <>
      <SpotlightCarousel games={games} />
      <MatchCenterDashboard />
    </>
  );
};

export default HomeView;