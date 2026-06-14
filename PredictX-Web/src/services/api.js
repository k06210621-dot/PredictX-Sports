import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1'; // Adjust if needed

export const fetchGamesByDate = async (dateStr) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/games`, {
      params: { date: dateStr },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching games:', error);
    throw error;
  }
};

export const fetchGameDetail = async (gameId) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/games/${gameId}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching game detail:', error);
    throw error;
  }
};

export const fetchLeagueGames = async (league, dateStr) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/games`, {
      params: { league, date: dateStr },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching league games:', error);
    throw error;
  }
};