--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4 (Homebrew)
-- Dumped by pg_dump version 18.4 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: predictx; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA predictx;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: predictx; Owner: -
--

CREATE FUNCTION predictx.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: game_analysis; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.game_analysis (
    analysis_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    game_id uuid,
    analysis_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: game_events; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.game_events (
    event_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    game_id uuid,
    play_number integer,
    distance_from_end integer,
    down integer,
    yards_to_go integer,
    play_type character varying(100),
    description text,
    result character varying(255),
    is_touchdown boolean DEFAULT false,
    is_interception boolean DEFAULT false,
    yardage_gain integer,
    play_time text,
    play_index integer,
    season integer NOT NULL,
    week integer,
    quarter integer,
    clock_in_quarter character varying(10),
    home_team_id uuid,
    away_team_id uuid,
    play_index_offset integer,
    play_sequence character varying(50),
    "timestamp" integer
);


--
-- Name: game_stats; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.game_stats (
    stat_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    game_id uuid,
    team_id uuid,
    player_id uuid,
    stat_type character varying(100) NOT NULL,
    value double precision NOT NULL,
    is_offensive boolean DEFAULT false,
    is_defensive boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: game_status; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.game_status (
    game_status_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    game_id uuid NOT NULL,
    status character varying(50) NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: games; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.games (
    game_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    season integer NOT NULL,
    week integer,
    match_date date NOT NULL,
    status character varying(50) DEFAULT 'SCHEDULED'::character varying,
    home_team_id uuid,
    away_team_id uuid,
    home_venue_id uuid,
    home_team_score double precision,
    away_team_score double precision,
    broadcast_network character varying(100),
    broadcast_time text,
    notes text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: historical_matchups; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.historical_matchups (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    home_team_id uuid NOT NULL,
    away_team_id uuid NOT NULL,
    as_of_date date NOT NULL,
    total_played integer DEFAULT 0 NOT NULL,
    home_wins integer DEFAULT 0 NOT NULL,
    away_wins integer DEFAULT 0 NOT NULL,
    avg_home_score numeric(5,2),
    avg_away_score numeric(5,2),
    last_5_games_result character varying(50),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    league_id uuid
);


--
-- Name: ingestion_logs; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.ingestion_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    run_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    league_code character varying(10),
    records_fetched integer,
    records_inserted integer,
    records_updated integer,
    status character varying(20) DEFAULT 'success'::character varying,
    error_message text,
    duration_ms integer,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: injuries; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.injuries (
    injury_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    player_uuid uuid,
    player_name character varying(255) NOT NULL,
    team_id uuid,
    injury_date date NOT NULL,
    injury_type character varying(255),
    recovery_date date,
    recovery_percentage double precision,
    status character varying(50) DEFAULT 'INJURED'::character varying,
    notes text
);


--
-- Name: leagues; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.leagues (
    league_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(255) NOT NULL,
    sport_type character varying(100),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: news; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.news (
    news_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    season integer NOT NULL,
    week integer,
    team_id uuid,
    headline character varying(500) NOT NULL,
    summary text,
    source character varying(255),
    published_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    raw_url text
);


--
-- Name: odds; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    game_id uuid NOT NULL,
    sportsbook_id uuid NOT NULL,
    odds_timestamp timestamp with time zone NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
)
PARTITION BY RANGE (odds_timestamp);


--
-- Name: odds_default; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds_default (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT odds_id_not_null NOT NULL,
    game_id uuid CONSTRAINT odds_game_id_not_null NOT NULL,
    sportsbook_id uuid CONSTRAINT odds_sportsbook_id_not_null NOT NULL,
    odds_timestamp timestamp with time zone CONSTRAINT odds_odds_timestamp_not_null NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_updated_at_not_null NOT NULL
);


--
-- Name: odds_y2026_q1; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds_y2026_q1 (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT odds_id_not_null NOT NULL,
    game_id uuid CONSTRAINT odds_game_id_not_null NOT NULL,
    sportsbook_id uuid CONSTRAINT odds_sportsbook_id_not_null NOT NULL,
    odds_timestamp timestamp with time zone CONSTRAINT odds_odds_timestamp_not_null NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_updated_at_not_null NOT NULL
);


--
-- Name: odds_y2026_q2; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds_y2026_q2 (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT odds_id_not_null NOT NULL,
    game_id uuid CONSTRAINT odds_game_id_not_null NOT NULL,
    sportsbook_id uuid CONSTRAINT odds_sportsbook_id_not_null NOT NULL,
    odds_timestamp timestamp with time zone CONSTRAINT odds_odds_timestamp_not_null NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_updated_at_not_null NOT NULL
);


--
-- Name: odds_y2026_q3; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds_y2026_q3 (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT odds_id_not_null NOT NULL,
    game_id uuid CONSTRAINT odds_game_id_not_null NOT NULL,
    sportsbook_id uuid CONSTRAINT odds_sportsbook_id_not_null NOT NULL,
    odds_timestamp timestamp with time zone CONSTRAINT odds_odds_timestamp_not_null NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_updated_at_not_null NOT NULL
);


--
-- Name: odds_y2026_q4; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.odds_y2026_q4 (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT odds_id_not_null NOT NULL,
    game_id uuid CONSTRAINT odds_game_id_not_null NOT NULL,
    sportsbook_id uuid CONSTRAINT odds_sportsbook_id_not_null NOT NULL,
    odds_timestamp timestamp with time zone CONSTRAINT odds_odds_timestamp_not_null NOT NULL,
    home_ml numeric(10,2),
    away_ml numeric(10,2),
    home_spread numeric(10,2),
    away_spread numeric(10,2),
    spread_line numeric(10,2),
    over_line numeric(10,2),
    under_line numeric(10,2),
    over_under_value numeric(10,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT odds_updated_at_not_null NOT NULL
);


--
-- Name: player_aliases; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.player_aliases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    player_id uuid NOT NULL,
    alias_name character varying(150) NOT NULL,
    source_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: player_stats; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.player_stats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    game_id uuid NOT NULL,
    player_id uuid NOT NULL,
    team_id uuid NOT NULL,
    playing_time character varying(20),
    stats jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: player_teams; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.player_teams (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    player_id uuid,
    team_id uuid,
    is_active boolean DEFAULT true
);


--
-- Name: players; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.players (
    player_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    player_name character varying(255) NOT NULL,
    team_id uuid,
    "position" character varying(50),
    height character varying(10),
    weight integer,
    jersey_number integer,
    date_of_birth date,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    external_id character varying(50)
);


--
-- Name: referees; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.referees (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    league_id uuid NOT NULL,
    full_name character varying(150) NOT NULL,
    chinese_name character varying(150),
    experience_years integer,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: rosters; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.rosters (
    season integer NOT NULL,
    roster_date date NOT NULL,
    team_id uuid NOT NULL,
    player_uuid uuid NOT NULL,
    jersey_number integer,
    "position" character varying(50),
    is_active boolean DEFAULT true
);


--
-- Name: schedules; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.schedules (
    schedule_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    game_id uuid NOT NULL,
    source_name character varying(255) NOT NULL,
    raw_payload jsonb NOT NULL,
    checksum text NOT NULL,
    season integer,
    division_id character varying(100),
    division_name character varying(255),
    conference character varying(255),
    team_id uuid,
    match_date date,
    opponent_name character varying(255),
    opponent_short_name character varying(100),
    home_or_away character varying(10) DEFAULT 'HOME'::character varying,
    status character varying(50) DEFAULT 'SCHEDULED'::character varying,
    notes character varying(255)
);


--
-- Name: seasons; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.seasons (
    season_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    league_id uuid,
    year integer NOT NULL,
    start_date date,
    end_date date,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: sportsbooks; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.sportsbooks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: standings; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.standings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    season_id uuid NOT NULL,
    team_id uuid NOT NULL,
    as_of_date date NOT NULL,
    wins integer DEFAULT 0 NOT NULL,
    losses integer DEFAULT 0 NOT NULL,
    draws integer DEFAULT 0 NOT NULL,
    win_percentage numeric(5,4) DEFAULT 0.0000 NOT NULL,
    streak character varying(20),
    points integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: team_aliases; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.team_aliases (
    alias_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    team_id uuid,
    alias_name character varying(255) NOT NULL,
    source_name character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: team_stats; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.team_stats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    game_id uuid NOT NULL,
    team_id uuid NOT NULL,
    stats jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: team_venues; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.team_venues (
    team_id uuid NOT NULL,
    venue_id uuid NOT NULL,
    is_home_venue boolean DEFAULT false
);


--
-- Name: teams; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.teams (
    team_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    team_code character varying(20) NOT NULL,
    english_name character varying(255) NOT NULL,
    chinese_name character varying(255) NOT NULL,
    abbreviation character varying(10) NOT NULL,
    league character varying(100) NOT NULL,
    division character varying(100),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: venues; Type: TABLE; Schema: predictx; Owner: -
--

CREATE TABLE predictx.venues (
    venue_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    venue_name character varying(255) NOT NULL,
    city character varying(100) NOT NULL,
    state character varying(100),
    country character varying(100) DEFAULT 'USA'::character varying,
    capacity integer,
    surface character varying(100)
);


--
-- Name: v_ai_matchup_features; Type: VIEW; Schema: predictx; Owner: -
--

CREATE VIEW predictx.v_ai_matchup_features AS
 WITH team_form AS (
         SELECT t.league,
            g_1.home_team_id AS team_id,
            avg(g_1.home_team_score) AS avg_points_for,
            avg(g_1.away_team_score) AS avg_points_against,
            avg((g_1.home_team_score - g_1.away_team_score)) AS avg_margin,
            count(*) FILTER (WHERE (g_1.home_team_score > g_1.away_team_score)) AS wins_last5,
            count(*) AS games_played
           FROM ((predictx.games g_1
             JOIN predictx.teams t ON ((g_1.home_team_id = t.team_id)))
             JOIN predictx.game_status gs_1 ON ((g_1.game_id = gs_1.game_id)))
          WHERE (((gs_1.status)::text = 'FINAL'::text) AND (g_1.home_team_score IS NOT NULL) AND (g_1.away_team_score IS NOT NULL) AND (g_1.match_date >= (CURRENT_DATE - '30 days'::interval)))
          GROUP BY t.league, g_1.home_team_id
        UNION ALL
         SELECT t.league,
            g_1.away_team_id AS team_id,
            avg(g_1.away_team_score) AS avg_points_for,
            avg(g_1.home_team_score) AS avg_points_against,
            avg((g_1.away_team_score - g_1.home_team_score)) AS avg_margin,
            count(*) FILTER (WHERE (g_1.away_team_score > g_1.home_team_score)) AS wins_last5,
            count(*) AS games_played
           FROM ((predictx.games g_1
             JOIN predictx.teams t ON ((g_1.away_team_id = t.team_id)))
             JOIN predictx.game_status gs_1 ON ((g_1.game_id = gs_1.game_id)))
          WHERE (((gs_1.status)::text = 'FINAL'::text) AND (g_1.home_team_score IS NOT NULL) AND (g_1.away_team_score IS NOT NULL) AND (g_1.match_date >= (CURRENT_DATE - '30 days'::interval)))
          GROUP BY t.league, g_1.away_team_id
        ), injury_counts AS (
         SELECT injuries.team_id,
            count(*) AS injured_count
           FROM predictx.injuries
          WHERE ((injuries.recovery_date IS NULL) OR (injuries.recovery_percentage < (100)::double precision))
          GROUP BY injuries.team_id
        ), latest_odds AS (
         SELECT DISTINCT ON (odds.game_id) odds.game_id,
            odds.home_ml AS moneyline_home,
            odds.away_ml AS moneyline_away,
            ((odds.home_spread + odds.away_spread) / (2)::numeric) AS point_spread,
            odds.over_under_value AS total_over,
            odds.over_under_value AS total_under
           FROM predictx.odds
          ORDER BY odds.game_id, odds.odds_timestamp DESC
        ), standings_snapshot AS (
         SELECT standings.team_id,
            standings.wins,
            standings.losses,
            standings.win_percentage AS win_pct,
            0 AS games_behind,
            standings.streak
           FROM predictx.standings
          WHERE (standings.as_of_date = ( SELECT max(standings_1.as_of_date) AS max
                   FROM predictx.standings standings_1))
        )
 SELECT g.game_id,
    t1.league,
    g.season,
    g.match_date,
    NULL::text AS game_time,
    g.home_team_id,
    g.away_team_id,
    t1.english_name AS home_team_name,
    t2.english_name AS away_team_name,
    g.home_team_score,
    g.away_team_score,
    gs.status,
    tf1.avg_points_for AS home_avg_points_last5,
    tf1.avg_points_against AS home_avg_points_allowed_last5,
    tf1.avg_margin AS home_avg_margin_last5,
    tf1.wins_last5 AS home_wins_last5,
    tf1.games_played AS home_games_played,
    tf2.avg_points_for AS away_avg_points_last5,
    tf2.avg_points_against AS away_avg_points_allowed_last5,
    tf2.avg_margin AS away_avg_margin_last5,
    tf2.wins_last5 AS away_wins_last5,
    tf2.games_played AS away_games_played,
    hm.total_played AS h2h_total_played,
    hm.home_wins AS h2h_home_wins,
    hm.away_wins AS h2h_away_wins,
        CASE
            WHEN (hm.total_played > 0) THEN round((((hm.home_wins)::numeric / (hm.total_played)::numeric) * (100)::numeric), 2)
            ELSE (0)::numeric
        END AS h2h_win_pct_home,
    hm.avg_home_score AS h2h_avg_home_score,
    hm.avg_away_score AS h2h_avg_away_score,
        CASE
            WHEN (hm.total_played > 0) THEN round((hm.avg_home_score - hm.avg_away_score), 2)
            ELSE (0)::numeric
        END AS h2h_avg_margin,
    hm.last_5_games_result AS h2h_last_5_results,
    COALESCE(ic1.injured_count, (0)::bigint) AS home_injured_count,
    COALESCE(ic2.injured_count, (0)::bigint) AS away_injured_count,
    lo.moneyline_home,
    lo.moneyline_away,
    lo.point_spread,
    lo.total_over,
    lo.total_under,
    s1.win_pct AS home_win_pct,
    s1.streak AS home_streak,
    s2.win_pct AS away_win_pct,
    s2.streak AS away_streak,
    v.venue_name,
    NULL::text AS attendance,
    g.created_at,
    g.updated_at
   FROM ((((((((((((predictx.games g
     JOIN predictx.teams t1 ON ((g.home_team_id = t1.team_id)))
     JOIN predictx.teams t2 ON ((g.away_team_id = t2.team_id)))
     JOIN predictx.game_status gs ON ((g.game_id = gs.game_id)))
     LEFT JOIN predictx.venues v ON ((g.home_venue_id = v.venue_id)))
     LEFT JOIN team_form tf1 ON ((((t1.league)::text = (tf1.league)::text) AND (g.home_team_id = tf1.team_id))))
     LEFT JOIN team_form tf2 ON ((((t2.league)::text = (tf2.league)::text) AND (g.away_team_id = tf2.team_id))))
     LEFT JOIN predictx.historical_matchups hm ON (((LEAST(g.home_team_id, g.away_team_id) = LEAST(hm.home_team_id, hm.away_team_id)) AND (GREATEST(g.home_team_id, g.away_team_id) = GREATEST(hm.home_team_id, hm.away_team_id)))))
     LEFT JOIN injury_counts ic1 ON ((g.home_team_id = ic1.team_id)))
     LEFT JOIN injury_counts ic2 ON ((g.away_team_id = ic2.team_id)))
     LEFT JOIN latest_odds lo ON ((g.game_id = lo.game_id)))
     LEFT JOIN standings_snapshot s1 ON ((g.home_team_id = s1.team_id)))
     LEFT JOIN standings_snapshot s2 ON ((g.away_team_id = s2.team_id)))
  ORDER BY g.match_date;


--
-- Name: odds_default; Type: TABLE ATTACH; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds ATTACH PARTITION predictx.odds_default DEFAULT;


--
-- Name: odds_y2026_q1; Type: TABLE ATTACH; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds ATTACH PARTITION predictx.odds_y2026_q1 FOR VALUES FROM ('2026-01-01 08:00:00+08') TO ('2026-04-01 08:00:00+08');


--
-- Name: odds_y2026_q2; Type: TABLE ATTACH; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds ATTACH PARTITION predictx.odds_y2026_q2 FOR VALUES FROM ('2026-04-01 08:00:00+08') TO ('2026-07-01 08:00:00+08');


--
-- Name: odds_y2026_q3; Type: TABLE ATTACH; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds ATTACH PARTITION predictx.odds_y2026_q3 FOR VALUES FROM ('2026-07-01 08:00:00+08') TO ('2026-10-01 08:00:00+08');


--
-- Name: odds_y2026_q4; Type: TABLE ATTACH; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds ATTACH PARTITION predictx.odds_y2026_q4 FOR VALUES FROM ('2026-10-01 08:00:00+08') TO ('2027-01-01 08:00:00+08');


--
-- Name: game_analysis game_analysis_game_id_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_analysis
    ADD CONSTRAINT game_analysis_game_id_key UNIQUE (game_id);


--
-- Name: game_analysis game_analysis_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_analysis
    ADD CONSTRAINT game_analysis_pkey PRIMARY KEY (analysis_id);


--
-- Name: game_events game_events_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_events
    ADD CONSTRAINT game_events_pkey PRIMARY KEY (event_id);


--
-- Name: game_events game_events_season_week_play_index_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_events
    ADD CONSTRAINT game_events_season_week_play_index_key UNIQUE (season, week, play_index);


--
-- Name: game_stats game_stats_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_stats
    ADD CONSTRAINT game_stats_pkey PRIMARY KEY (stat_id);


--
-- Name: game_status game_status_game_id_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_status
    ADD CONSTRAINT game_status_game_id_key UNIQUE (game_id);


--
-- Name: game_status game_status_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_status
    ADD CONSTRAINT game_status_pkey PRIMARY KEY (game_status_id);


--
-- Name: games games_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.games
    ADD CONSTRAINT games_pkey PRIMARY KEY (game_id);


--
-- Name: games games_season_match_date_home_team_id_away_team_id_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.games
    ADD CONSTRAINT games_season_match_date_home_team_id_away_team_id_key UNIQUE (season, match_date, home_team_id, away_team_id);


--
-- Name: historical_matchups historical_matchups_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.historical_matchups
    ADD CONSTRAINT historical_matchups_pkey PRIMARY KEY (id);


--
-- Name: ingestion_logs ingestion_logs_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.ingestion_logs
    ADD CONSTRAINT ingestion_logs_pkey PRIMARY KEY (id);


--
-- Name: injuries injuries_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.injuries
    ADD CONSTRAINT injuries_pkey PRIMARY KEY (injury_id);


--
-- Name: leagues leagues_code_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.leagues
    ADD CONSTRAINT leagues_code_key UNIQUE (code);


--
-- Name: leagues leagues_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.leagues
    ADD CONSTRAINT leagues_pkey PRIMARY KEY (league_id);


--
-- Name: news news_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.news
    ADD CONSTRAINT news_pkey PRIMARY KEY (news_id);


--
-- Name: news news_season_week_team_id_headline_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.news
    ADD CONSTRAINT news_season_week_team_id_headline_key UNIQUE (season, week, team_id, headline);


--
-- Name: odds odds_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds
    ADD CONSTRAINT odds_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: odds_default odds_default_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds_default
    ADD CONSTRAINT odds_default_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: odds_y2026_q1 odds_y2026_q1_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds_y2026_q1
    ADD CONSTRAINT odds_y2026_q1_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: odds_y2026_q2 odds_y2026_q2_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds_y2026_q2
    ADD CONSTRAINT odds_y2026_q2_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: odds_y2026_q3 odds_y2026_q3_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds_y2026_q3
    ADD CONSTRAINT odds_y2026_q3_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: odds_y2026_q4 odds_y2026_q4_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.odds_y2026_q4
    ADD CONSTRAINT odds_y2026_q4_pkey PRIMARY KEY (id, odds_timestamp);


--
-- Name: player_aliases player_aliases_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_aliases
    ADD CONSTRAINT player_aliases_pkey PRIMARY KEY (id);


--
-- Name: player_stats player_stats_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_stats
    ADD CONSTRAINT player_stats_pkey PRIMARY KEY (id);


--
-- Name: player_teams player_teams_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_teams
    ADD CONSTRAINT player_teams_pkey PRIMARY KEY (id);


--
-- Name: players players_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.players
    ADD CONSTRAINT players_pkey PRIMARY KEY (player_id);


--
-- Name: referees referees_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.referees
    ADD CONSTRAINT referees_pkey PRIMARY KEY (id);


--
-- Name: rosters rosters_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.rosters
    ADD CONSTRAINT rosters_pkey PRIMARY KEY (season, team_id, player_uuid);


--
-- Name: schedules schedules_checksum_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.schedules
    ADD CONSTRAINT schedules_checksum_key UNIQUE (checksum);


--
-- Name: schedules schedules_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.schedules
    ADD CONSTRAINT schedules_pkey PRIMARY KEY (schedule_id);


--
-- Name: seasons seasons_league_id_year_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.seasons
    ADD CONSTRAINT seasons_league_id_year_key UNIQUE (league_id, year);


--
-- Name: seasons seasons_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.seasons
    ADD CONSTRAINT seasons_pkey PRIMARY KEY (season_id);


--
-- Name: sportsbooks sportsbooks_name_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.sportsbooks
    ADD CONSTRAINT sportsbooks_name_key UNIQUE (name);


--
-- Name: sportsbooks sportsbooks_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.sportsbooks
    ADD CONSTRAINT sportsbooks_pkey PRIMARY KEY (id);


--
-- Name: standings standings_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.standings
    ADD CONSTRAINT standings_pkey PRIMARY KEY (id);


--
-- Name: team_aliases team_aliases_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_aliases
    ADD CONSTRAINT team_aliases_pkey PRIMARY KEY (alias_id);


--
-- Name: team_aliases team_aliases_team_id_alias_name_source_name_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_aliases
    ADD CONSTRAINT team_aliases_team_id_alias_name_source_name_key UNIQUE (team_id, alias_name, source_name);


--
-- Name: team_stats team_stats_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_stats
    ADD CONSTRAINT team_stats_pkey PRIMARY KEY (id);


--
-- Name: team_venues team_venues_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_venues
    ADD CONSTRAINT team_venues_pkey PRIMARY KEY (team_id, venue_id);


--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);


--
-- Name: teams teams_team_code_key; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.teams
    ADD CONSTRAINT teams_team_code_key UNIQUE (team_code);


--
-- Name: game_stats unique_game_player_stat; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_stats
    ADD CONSTRAINT unique_game_player_stat UNIQUE (game_id, player_id, stat_type);


--
-- Name: historical_matchups uq_historical_matchup; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.historical_matchups
    ADD CONSTRAINT uq_historical_matchup UNIQUE (home_team_id, away_team_id, as_of_date);


--
-- Name: player_aliases uq_player_alias; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_aliases
    ADD CONSTRAINT uq_player_alias UNIQUE (player_id, alias_name, source_name);


--
-- Name: player_stats uq_player_game; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_stats
    ADD CONSTRAINT uq_player_game UNIQUE (game_id, player_id);


--
-- Name: standings uq_standings; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.standings
    ADD CONSTRAINT uq_standings UNIQUE (season_id, team_id, as_of_date);


--
-- Name: team_stats uq_team_game; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_stats
    ADD CONSTRAINT uq_team_game UNIQUE (game_id, team_id);


--
-- Name: venues venues_pkey; Type: CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.venues
    ADD CONSTRAINT venues_pkey PRIMARY KEY (venue_id);


--
-- Name: idx_game_analysis_game_id; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_game_analysis_game_id ON predictx.game_analysis USING btree (game_id);


--
-- Name: idx_game_stats_game_id; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_game_stats_game_id ON predictx.game_stats USING btree (game_id);


--
-- Name: idx_game_stats_team_id; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_game_stats_team_id ON predictx.game_stats USING btree (team_id);


--
-- Name: idx_games_match_date; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_games_match_date ON predictx.games USING btree (match_date);


--
-- Name: idx_games_season_week; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_games_season_week ON predictx.games USING btree (season, week);


--
-- Name: idx_historical_home_away; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_historical_home_away ON predictx.historical_matchups USING btree (home_team_id, away_team_id);


--
-- Name: idx_injuries_player_uuid; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_injuries_player_uuid ON predictx.injuries USING btree (player_uuid);


--
-- Name: idx_news_season_week; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_news_season_week ON predictx.news USING btree (season, week);


--
-- Name: idx_odds_game; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_odds_game ON ONLY predictx.odds USING btree (game_id);


--
-- Name: idx_odds_sportsbook; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_odds_sportsbook ON ONLY predictx.odds USING btree (sportsbook_id);


--
-- Name: idx_odds_timestamp; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_odds_timestamp ON ONLY predictx.odds USING btree (odds_timestamp DESC);


--
-- Name: idx_player_alias_name_trgm; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_alias_name_trgm ON predictx.player_aliases USING gin (alias_name public.gin_trgm_ops);


--
-- Name: idx_player_aliases_player; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_aliases_player ON predictx.player_aliases USING btree (player_id);


--
-- Name: idx_player_stats_game; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_stats_game ON predictx.player_stats USING btree (game_id);


--
-- Name: idx_player_stats_gin; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_stats_gin ON predictx.player_stats USING gin (stats);


--
-- Name: idx_player_stats_player; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_stats_player ON predictx.player_stats USING btree (player_id);


--
-- Name: idx_player_stats_team; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_player_stats_team ON predictx.player_stats USING btree (team_id);


--
-- Name: idx_players_external_id; Type: INDEX; Schema: predictx; Owner: -
--

CREATE UNIQUE INDEX idx_players_external_id ON predictx.players USING btree (external_id);


--
-- Name: idx_referees_league; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_referees_league ON predictx.referees USING btree (league_id);


--
-- Name: idx_rosters_season_team; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_rosters_season_team ON predictx.rosters USING btree (season, team_id);


--
-- Name: idx_schedules_season_date; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_schedules_season_date ON predictx.schedules USING btree (season, match_date);


--
-- Name: idx_standings_date; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_standings_date ON predictx.standings USING btree (as_of_date DESC);


--
-- Name: idx_standings_season; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_standings_season ON predictx.standings USING btree (season_id);


--
-- Name: idx_standings_team; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_standings_team ON predictx.standings USING btree (team_id);


--
-- Name: idx_team_stats_game; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_team_stats_game ON predictx.team_stats USING btree (game_id);


--
-- Name: idx_team_stats_gin; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_team_stats_gin ON predictx.team_stats USING gin (stats);


--
-- Name: idx_team_stats_team; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX idx_team_stats_team ON predictx.team_stats USING btree (team_id);


--
-- Name: odds_default_game_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_default_game_id_idx ON predictx.odds_default USING btree (game_id);


--
-- Name: odds_default_odds_timestamp_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_default_odds_timestamp_idx ON predictx.odds_default USING btree (odds_timestamp DESC);


--
-- Name: odds_default_sportsbook_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_default_sportsbook_id_idx ON predictx.odds_default USING btree (sportsbook_id);


--
-- Name: odds_y2026_q1_game_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q1_game_id_idx ON predictx.odds_y2026_q1 USING btree (game_id);


--
-- Name: odds_y2026_q1_odds_timestamp_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q1_odds_timestamp_idx ON predictx.odds_y2026_q1 USING btree (odds_timestamp DESC);


--
-- Name: odds_y2026_q1_sportsbook_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q1_sportsbook_id_idx ON predictx.odds_y2026_q1 USING btree (sportsbook_id);


--
-- Name: odds_y2026_q2_game_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q2_game_id_idx ON predictx.odds_y2026_q2 USING btree (game_id);


--
-- Name: odds_y2026_q2_odds_timestamp_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q2_odds_timestamp_idx ON predictx.odds_y2026_q2 USING btree (odds_timestamp DESC);


--
-- Name: odds_y2026_q2_sportsbook_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q2_sportsbook_id_idx ON predictx.odds_y2026_q2 USING btree (sportsbook_id);


--
-- Name: odds_y2026_q3_game_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q3_game_id_idx ON predictx.odds_y2026_q3 USING btree (game_id);


--
-- Name: odds_y2026_q3_odds_timestamp_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q3_odds_timestamp_idx ON predictx.odds_y2026_q3 USING btree (odds_timestamp DESC);


--
-- Name: odds_y2026_q3_sportsbook_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q3_sportsbook_id_idx ON predictx.odds_y2026_q3 USING btree (sportsbook_id);


--
-- Name: odds_y2026_q4_game_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q4_game_id_idx ON predictx.odds_y2026_q4 USING btree (game_id);


--
-- Name: odds_y2026_q4_odds_timestamp_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q4_odds_timestamp_idx ON predictx.odds_y2026_q4 USING btree (odds_timestamp DESC);


--
-- Name: odds_y2026_q4_sportsbook_id_idx; Type: INDEX; Schema: predictx; Owner: -
--

CREATE INDEX odds_y2026_q4_sportsbook_id_idx ON predictx.odds_y2026_q4 USING btree (sportsbook_id);


--
-- Name: odds_default_game_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_game ATTACH PARTITION predictx.odds_default_game_id_idx;


--
-- Name: odds_default_odds_timestamp_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_timestamp ATTACH PARTITION predictx.odds_default_odds_timestamp_idx;


--
-- Name: odds_default_pkey; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.odds_pkey ATTACH PARTITION predictx.odds_default_pkey;


--
-- Name: odds_default_sportsbook_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_sportsbook ATTACH PARTITION predictx.odds_default_sportsbook_id_idx;


--
-- Name: odds_y2026_q1_game_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_game ATTACH PARTITION predictx.odds_y2026_q1_game_id_idx;


--
-- Name: odds_y2026_q1_odds_timestamp_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_timestamp ATTACH PARTITION predictx.odds_y2026_q1_odds_timestamp_idx;


--
-- Name: odds_y2026_q1_pkey; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.odds_pkey ATTACH PARTITION predictx.odds_y2026_q1_pkey;


--
-- Name: odds_y2026_q1_sportsbook_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_sportsbook ATTACH PARTITION predictx.odds_y2026_q1_sportsbook_id_idx;


--
-- Name: odds_y2026_q2_game_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_game ATTACH PARTITION predictx.odds_y2026_q2_game_id_idx;


--
-- Name: odds_y2026_q2_odds_timestamp_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_timestamp ATTACH PARTITION predictx.odds_y2026_q2_odds_timestamp_idx;


--
-- Name: odds_y2026_q2_pkey; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.odds_pkey ATTACH PARTITION predictx.odds_y2026_q2_pkey;


--
-- Name: odds_y2026_q2_sportsbook_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_sportsbook ATTACH PARTITION predictx.odds_y2026_q2_sportsbook_id_idx;


--
-- Name: odds_y2026_q3_game_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_game ATTACH PARTITION predictx.odds_y2026_q3_game_id_idx;


--
-- Name: odds_y2026_q3_odds_timestamp_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_timestamp ATTACH PARTITION predictx.odds_y2026_q3_odds_timestamp_idx;


--
-- Name: odds_y2026_q3_pkey; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.odds_pkey ATTACH PARTITION predictx.odds_y2026_q3_pkey;


--
-- Name: odds_y2026_q3_sportsbook_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_sportsbook ATTACH PARTITION predictx.odds_y2026_q3_sportsbook_id_idx;


--
-- Name: odds_y2026_q4_game_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_game ATTACH PARTITION predictx.odds_y2026_q4_game_id_idx;


--
-- Name: odds_y2026_q4_odds_timestamp_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_timestamp ATTACH PARTITION predictx.odds_y2026_q4_odds_timestamp_idx;


--
-- Name: odds_y2026_q4_pkey; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.odds_pkey ATTACH PARTITION predictx.odds_y2026_q4_pkey;


--
-- Name: odds_y2026_q4_sportsbook_id_idx; Type: INDEX ATTACH; Schema: predictx; Owner: -
--

ALTER INDEX predictx.idx_odds_sportsbook ATTACH PARTITION predictx.odds_y2026_q4_sportsbook_id_idx;


--
-- Name: historical_matchups trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.historical_matchups FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: ingestion_logs trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.ingestion_logs FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: odds_default trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.odds_default FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: odds_y2026_q1 trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.odds_y2026_q1 FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: odds_y2026_q2 trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.odds_y2026_q2 FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: odds_y2026_q3 trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.odds_y2026_q3 FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: odds_y2026_q4 trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.odds_y2026_q4 FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: player_aliases trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.player_aliases FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: player_stats trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.player_stats FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: referees trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.referees FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: sportsbooks trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.sportsbooks FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: standings trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.standings FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: team_stats trg_update_updated_at; Type: TRIGGER; Schema: predictx; Owner: -
--

CREATE TRIGGER trg_update_updated_at BEFORE UPDATE ON predictx.team_stats FOR EACH ROW EXECUTE FUNCTION predictx.update_updated_at_column();


--
-- Name: game_analysis game_analysis_game_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_analysis
    ADD CONSTRAINT game_analysis_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;


--
-- Name: game_events game_events_away_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_events
    ADD CONSTRAINT game_events_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES predictx.teams(team_id);


--
-- Name: game_events game_events_game_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_events
    ADD CONSTRAINT game_events_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;


--
-- Name: game_events game_events_home_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_events
    ADD CONSTRAINT game_events_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES predictx.teams(team_id);


--
-- Name: game_stats game_stats_game_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_stats
    ADD CONSTRAINT game_stats_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;


--
-- Name: game_stats game_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_stats
    ADD CONSTRAINT game_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES predictx.players(player_id) ON DELETE SET NULL;


--
-- Name: game_stats game_stats_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_stats
    ADD CONSTRAINT game_stats_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: game_status game_status_game_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.game_status
    ADD CONSTRAINT game_status_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id) ON DELETE CASCADE;


--
-- Name: games games_away_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.games
    ADD CONSTRAINT games_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES predictx.teams(team_id);


--
-- Name: games games_home_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.games
    ADD CONSTRAINT games_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES predictx.teams(team_id);


--
-- Name: games games_home_venue_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.games
    ADD CONSTRAINT games_home_venue_id_fkey FOREIGN KEY (home_venue_id) REFERENCES predictx.venues(venue_id);


--
-- Name: injuries injuries_player_uuid_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.injuries
    ADD CONSTRAINT injuries_player_uuid_fkey FOREIGN KEY (player_uuid) REFERENCES predictx.players(player_id) ON DELETE CASCADE;


--
-- Name: injuries injuries_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.injuries
    ADD CONSTRAINT injuries_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: news news_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.news
    ADD CONSTRAINT news_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: odds odds_sportsbook_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE predictx.odds
    ADD CONSTRAINT odds_sportsbook_id_fkey FOREIGN KEY (sportsbook_id) REFERENCES predictx.sportsbooks(id) ON DELETE CASCADE;


--
-- Name: player_teams player_teams_player_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_teams
    ADD CONSTRAINT player_teams_player_id_fkey FOREIGN KEY (player_id) REFERENCES predictx.players(player_id) ON DELETE CASCADE;


--
-- Name: player_teams player_teams_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.player_teams
    ADD CONSTRAINT player_teams_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: players players_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.players
    ADD CONSTRAINT players_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE SET NULL;


--
-- Name: rosters rosters_player_uuid_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.rosters
    ADD CONSTRAINT rosters_player_uuid_fkey FOREIGN KEY (player_uuid) REFERENCES predictx.players(player_id) ON DELETE SET NULL;


--
-- Name: rosters rosters_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.rosters
    ADD CONSTRAINT rosters_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: schedules schedules_game_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.schedules
    ADD CONSTRAINT schedules_game_id_fkey FOREIGN KEY (game_id) REFERENCES predictx.games(game_id);


--
-- Name: schedules schedules_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.schedules
    ADD CONSTRAINT schedules_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: seasons seasons_league_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.seasons
    ADD CONSTRAINT seasons_league_id_fkey FOREIGN KEY (league_id) REFERENCES predictx.leagues(league_id) ON DELETE CASCADE;


--
-- Name: team_aliases team_aliases_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_aliases
    ADD CONSTRAINT team_aliases_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: team_venues team_venues_team_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_venues
    ADD CONSTRAINT team_venues_team_id_fkey FOREIGN KEY (team_id) REFERENCES predictx.teams(team_id) ON DELETE CASCADE;


--
-- Name: team_venues team_venues_venue_id_fkey; Type: FK CONSTRAINT; Schema: predictx; Owner: -
--

ALTER TABLE ONLY predictx.team_venues
    ADD CONSTRAINT team_venues_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES predictx.venues(venue_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


