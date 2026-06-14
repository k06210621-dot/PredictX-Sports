import React from 'react';
import { motion } from 'framer-motion';

const SpotlightCarousel = ({ games }) => {
  return (
    <section className="mb-8">
      <h2 className="mb-4 text-2xl font-bold text-light-text">今日焦點賽事</h2>
      <div className="overflow-x-auto space-x-4">
        {games.map((game, index) => (
          <motion.div
            key={index}
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: index * 0.1, type: 'spring', stiffness: 300, damping: 20 }}
            className="flex-shrink-0 w-72 bg-dark-card/50 backdrop-blur-sm rounded-xl border border-border/50 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-text">{game.awayTeam}</span>
              <span className="text-sm font-medium text-muted-text">@</span>
              <span className="text-sm font-medium text-muted-text">{game.homeTeam}</span>
            </div>
            <div className="text-center">
              <div className="mb-2">
                <span className="text-xl font-bold">{game.awayScore ?? '-'}</span>
                <span className="mx-2 text-xs">-</span>
                <span className="text-xl font-bold">{game.homeScore ?? '-'}</span>
              </div>
              <div className="flex items-center justify-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-xs text-green-500">Live</span>
              </div>
            </div>
            <div className="mt-2 text-xs text-muted-text">
              {game.venue}
            </div>
            <div className="mt-2">
              <div className="flex justify-between">
                <span>AI 勝率</span>
                <span className="font-medium">{game.aiWinRateHome?.toFixed(0)}%</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
};

export default SpotlightCarousel;