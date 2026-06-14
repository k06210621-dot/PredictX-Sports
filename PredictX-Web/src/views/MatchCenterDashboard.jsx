import React, { useState } from 'react';

const MatchCenterDashboard = () => {
  const [activeTab, setActiveTab] = useState('yesterday'); // yesterday, today, tomorrow
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchGames = async (dateStr) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGamesByDate(dateStr);
      setGames(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadInitial = async () => {
      const today = new Date().toISOString().split('T')[0];
      await fetchGames(today);
    };
    loadInitial();
  }, []);

  const handleTabChange = async (tab) => {
    setActiveTab(tab);
    let dateStr = '';
    if (tab === 'yesterday') {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      dateStr = yesterday.toISOString().split('T')[0];
    } else if (tab === 'today') {
      dateStr = new Date().toISOString().split('T')[0];
    } else if (tab === 'tomorrow') {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      dateStr = tomorrow.toISOString().split('T')[0];
    }
    await fetchGames(dateStr);
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-pulse w-8 h-8 border-2 border-primary/50 border-t-primary rounded-full"></div>
        <p className="mt-2 text-muted-text">載入賽事中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-500">
        <p className="mb-2">載入失敗: {error}</p>
        <button
          onClick={() => {
            const today = new Date().toISOString().split('T')[0];
            fetchGames(today);
          }}
          className="bg-primary hover:bg-primary/90 text-white font-medium py-2 px-4 rounded transition-colors"
        >
          重新載入
        </button>
      </div>
    );
  }

  return (
    <section className="mb-8">
      <h2 className="mb-4 text-2xl font-bold text-light-text">即時球賽中心</h2>
      <div className="flex mb-4">
        <button
          onClick={() => handleTabChange('yesterday')}
          className={`flex-1 px-4 py-2 text-sm font-medium 
                     ${activeTab === 'yesterday' 
                       ? 'bg-primary text-white' 
                       : 'bg-transparent text-muted-text hover:bg-dark-card/50'}
                     transition-colors duration-200`}
        >
          昨日戰績
        </button>
        <button
          onClick={() => handleTabChange('today')}
          className={`flex-1 px-4 py-2 text-sm font-medium 
                     ${activeTab === 'today' 
                       ? 'bg-primary text-white' 
                       : 'bg-transparent text-muted-text hover:bg-dark-card/50'}
                     transition-colors duration-200`}
        >
          今日即時比分
        </button>
        <button
          onClick={() => handleTabChange('tomorrow')}
          className={`flex-1 px-4 py-2 text-sm font-medium 
                     ${activeTab === 'tomorrow' 
                       ? 'bg-primary text-white' 
                       : 'bg-transparent text-muted-text hover:bg-dark-card/50'}
                     transition-colors duration-200`}
        >
          明日預告
        </button>
      </div>

      <div className="space-y-4">
        {games.map((game, index) => (
          <motion.div
            key={game.id || index}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: index * 0.05 }}
            className="bg-dark-card/50 backdrop-blur-sm rounded-xl border border-border/50 overflow-hidden"
          >
            <div className="cursor-pointer p-4" onClick={() => setExpanded(!expanded)}>
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-muted-text">
                    {game.awayTeam} @ {game.homeTeam}
                  </p>
                  <p className="flex items-center space-x-2 mt-1">
                    <span className="text-xs">{game.venue}</span>
                    <span className="w-0.5 h-0.5 bg-gray-400 rounded-full"></span>
                    <span className="text-xs">{game.startTime?.substring(11, 16)}</span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg">
                    {game.awayScore ?? '-'} - {game.homeScore ?? '-'}
                  </p>
                  <p className="text-xs text-muted-text">
                    {game.status?.toUpperCase() ?? 'SCHEDULED'}
                  </p>
                </div>
                <div className="ml-3">
                  <span className={`inline-block h-4 w-4 rounded-full 
                                 ${game.status === 'Final' ? 'bg-green-500' 
                                   : game.status === 'In Progress' ? 'bg-yellow-500' 
                                   : 'bg-gray-400'}`}></span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs font-medium text-muted-text">
                  AI 勝率: {game.aiWinRateHome?.toFixed(0)}%
                </span>
                <span className="text-xs">
                  {expanded ? '▲ 收起' : '▼ 展開'}
                </span>
              </div>
            </div>

            {expanded && (
              <div className="border-t border-border/50">
                <div className="p-4 space-y-3">
                  <div className="text-sm text-muted-text">
                    <span className="font-medium">歷史對戰:</span> {game.h2hRecord ?? '暫無數據'}
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="font-medium">客隊 KPI:</span>
                      <p className="mt-1">
                        WHIP: {game.awayWhip ?? '-'} | ERA: {game.awayEra ?? '-'} | K/9: {game.awayK9 ?? '-'}
                      </p>
                    </div>
                    <div>
                      <span className="font-medium">主隊 KPI:</span>
                      <p className="mt-1">
                        WHIP: {game.homeWhip ?? '-'} | ERA: {game.homeEra ?? '-'} | K/9: {game.homeK9 ?? '-'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </div>
    </section>
  );
};

export default MatchCenterDashboard;