--
-- PredictX Advanced Schema Migration
-- 新增 predictx_advanced schema 與進階分析表格
-- 用於 MLB/NBA 進階數據、天氣、盤口資料
--

CREATE SCHEMA IF NOT EXISTS predictx_advanced;

-- 天氣資料
CREATE TABLE IF NOT EXISTS predictx_advanced.game_weather (
    game_id uuid NOT NULL,
    venue_name text,
    temperature numeric(4,1),
    wind_speed numeric(4,1),
    wind_direction text,
    humidity numeric(4,1),
    precipitation_pct numeric(4,1),
    data_source text DEFAULT 'openweathermap'::text,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- 盤口/市場資料
CREATE TABLE IF NOT EXISTS predictx_advanced.market_data (
    game_id uuid NOT NULL,
    home_moneyline integer,
    away_moneyline integer,
    run_line_home numeric(4,1),
    run_line_away numeric(4,1),
    over_under numeric(4,1),
    data_source text,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- MLB 投手數據
CREATE TABLE IF NOT EXISTS predictx_advanced.mlb_pitcher_stats (
    game_id uuid NOT NULL,
    team_id uuid NOT NULL,
    pitcher_name text NOT NULL,
    era numeric(5,2),
    whip numeric(5,3),
    k_per_9 numeric(5,2),
    bb_per_9 numeric(5,2),
    last_5_era numeric(5,2),
    data_source text DEFAULT 'statsapi.mlb.com'::text,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- MLB 團隊數據
CREATE TABLE IF NOT EXISTS predictx_advanced.mlb_team_stats (
    game_id uuid NOT NULL,
    team_id uuid NOT NULL,
    last_10_winrate numeric(4,3),
    home_winrate numeric(4,3),
    road_winrate numeric(4,3),
    team_ops numeric(5,3),
    team_obp numeric(5,3),
    team_slg numeric(5,3),
    bullpen_era numeric(5,2),
    data_source text DEFAULT 'statsapi.mlb.com'::text,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- NBA 團隊數據
CREATE TABLE IF NOT EXISTS predictx_advanced.nba_team_stats (
    game_id uuid NOT NULL,
    team_id uuid NOT NULL,
    off_rtg numeric(6,1),
    def_rtg numeric(6,1),
    net_rating numeric(6,1),
    pace numeric(5,1),
    efg_pct numeric(5,3),
    ts_pct numeric(5,3),
    ast_pct numeric(5,3),
    reb_pct numeric(5,3),
    tov_pct numeric(5,3),
    win_pct numeric(4,3),
    data_source text DEFAULT 'nba_api'::text,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- 主鍵
ALTER TABLE ONLY predictx_advanced.game_weather
    ADD CONSTRAINT game_weather_pkey PRIMARY KEY (game_id);

ALTER TABLE ONLY predictx_advanced.market_data
    ADD CONSTRAINT market_data_pkey PRIMARY KEY (game_id);

ALTER TABLE ONLY predictx_advanced.mlb_pitcher_stats
    ADD CONSTRAINT mlb_pitcher_stats_pkey PRIMARY KEY (game_id, team_id, pitcher_name);

ALTER TABLE ONLY predictx_advanced.mlb_team_stats
    ADD CONSTRAINT mlb_team_stats_pkey PRIMARY KEY (game_id, team_id);

ALTER TABLE ONLY predictx_advanced.nba_team_stats
    ADD CONSTRAINT nba_team_stats_pkey PRIMARY KEY (game_id, team_id);

-- 外鍵
ALTER TABLE ONLY predictx_advanced.game_weather
    ADD CONSTRAINT game_weather_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;

ALTER TABLE ONLY predictx_advanced.market_data
    ADD CONSTRAINT market_data_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;

ALTER TABLE ONLY predictx_advanced.mlb_pitcher_stats
    ADD CONSTRAINT mlb_pitcher_stats_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;

ALTER TABLE ONLY predictx_advanced.mlb_pitcher_stats
    ADD CONSTRAINT mlb_pitcher_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id);

ALTER TABLE ONLY predictx_advanced.mlb_team_stats
    ADD CONSTRAINT mlb_team_stats_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;

ALTER TABLE ONLY predictx_advanced.mlb_team_stats
    ADD CONSTRAINT mlb_team_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id);

ALTER TABLE ONLY predictx_advanced.nba_team_stats
    ADD CONSTRAINT nba_team_stats_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;

ALTER TABLE ONLY predictx_advanced.nba_team_stats
    ADD CONSTRAINT nba_team_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id);
