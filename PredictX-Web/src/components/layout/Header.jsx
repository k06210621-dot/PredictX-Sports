import React from 'react';
import { LeagueType } from '../../models/LeagueType';

const Header = () => {
  const leagues = [
    { id: 'nba', name: 'NBA', color: 'from-blue-500 to-blue-600' },
    { id: 'mlb', name: 'MLB', color: 'from-red-500 to-red-600' },
    { id: 'npb', name: 'NPB', color: 'from-yellow-500 to-yellow-600' },
    { id: 'cpbl', name: 'CPBL', color: 'from-green-500 to-green-600' },
    { id: 'fifa', name: 'FIFA', color: 'from-purple-500 to-purple-600' },
  ];

  return (
    <header className="relative bg-dark-bg/90 backdrop-blur-sm">
      <div className="absolute inset-0 -z-10">
        <div className="h-[2px] bg-gradient-to-r from-blue-500 via-purple-500 to-red-500 animate-scan-line"></div>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex-shrink-0 flex items-center space-x-3">
            <span className="text-xl font-bold text-light-text">PredictX Sports</span>
          </div>
          <div className="hidden md:flex md:items-center md:space-x-4">
            {leagues.map(league => (
              <button
                key={league.id}
                className={`relative flex h-9 w-9 items-center justify-center rounded-full 
                           bg-gradient-to-br from-gray-800 to-gray-900 
                           hover:bg-gradient-to-br from-gray-700 to-gray-800 
                           transition-colors duration-200`}
              >
                <span className="absolute inset-0 rounded-full 
                           bg-gradient-to-br ${league.color} 
                           opacity-0 hover:opacity-100 transition-opacity duration-200"></span>
                <span className="relative z-10 text-sm font-medium text-light-text">
                  {league.name}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;