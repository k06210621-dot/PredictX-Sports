# PredictX Sports Web Frontend

A high-quality, responsive web frontend for sports data analysis and prediction, built with React, Vite, and Tailwind CSS.

## 🚀 Features

- Modern, tech-inspired UI (ESPN + Apple Sports aesthetic)
- Responsive design for all device sizes
- Real-time data integration with existing FastAPI backend
- League-specific views (NBA, MLB, NPB, CPBL, FIFA)
- Match center with yesterday/today/tomorrow tabs
- Expandable game cards with detailed statistics
- Smooth animations and transitions
- Dark mode optimized

## 📁 Project Structure

```
/src
  /assets
  /components
    /layout
      Header.jsx
    /ui
      (reusable UI components)
    SpotlightCarousel.jsx
  /services
    api.js           # API service for backend communication
  /views
    HomeView.jsx
    MatchCenterDashboard.jsx
  App.jsx
  main.jsx
  index.css
```

## 🔧 Setup Instructions

1. **Clone / Copy the project** to `/Users/jero/PredictX Sports/PredictX-Web`

2. **Install dependencies**:
   ```bash
   cd /Users/jero/PredictX Sports/PredictX-Web
   npm install
   ```

3. **Configure API endpoint**:
   - Open `/src/services/api.js`
   - Update `API_BASE_URL` if your backend runs on a different URL/port
   - Default: `http://localhost:8000/api/v1`

4. **Start the development server**:
   ```bash
   npm run dev
   ```

5. **Build for production**:
   ```bash
   npm run build
   ```

## 🔌 Backend Integration

This frontend expects the following API endpoints from your FastAPI backend (`/Users/jero/sports-ingestion`):

- `GET /api/v1/games?date=YYYY-MM-DD` - Get games for a specific date
- `GET /api/v1/games?league=LEAGUE&date=YYYY-MM-DD` - Get games filtered by league
- `GET /api/v1/games/{gameId}` - Get detailed game information

Ensure your FastAPI server is running and accessible before starting the frontend.

## 🎨 Customization

- **Colors**: Modify `tailwind.config.js` to adjust the color scheme
- **Typography**: Edit `src/index.css` for base styles
- **Components**: Reusable UI components can be added to `/src/components/ui`

## 🧩 Key Components

- `Header.jsx`: League selection buttons with animated gradient effects
- `SpotlightCarousel.jsx`: Horizontal scroll of featured games with motion animations
- `MatchCenterDashboard.jsx`: Tabbed interface with expandable game cards (Accordion style)
- `api.js`: Centralized API service with error handling

## ⚠️ Notes

- The frontend is designed to work with your existing PostgreSQL/FastAPI data model
- No hardcoded test data - all data comes from API endpoints
- Loading states and error handling implemented for robust UX
- Skeleton UI would be implemented in a production version (placeholder shown as loading states)