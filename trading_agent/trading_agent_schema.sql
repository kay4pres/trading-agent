-- Trading Agent Database Schema
-- Run this in pgAdmin against the mindgentic_dev database
-- Creates the app_data schema and tables for the AI Trading Agent

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS trading_agent;

-- Table: trading_rules
-- Stores knowledge extracted from Warrior Trading courses
CREATE TABLE IF NOT EXISTS trading_agent.trading_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    category VARCHAR(100), -- e.g. entry, exit, risk_management, setup
    description TEXT,
    conditions TEXT,
    action_recommendation VARCHAR(50), -- BUY, SELL, HOLD
    source_lesson VARCHAR(255),
    confidence_score DECIMAL(3,2), -- 0.00 - 1.00
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: trade_history
-- Records all paper trades executed
CREATE TABLE IF NOT EXISTS trading_agent.trade_history (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    trade_action VARCHAR(10) NOT NULL, -- BUY or SELL
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    pnl DECIMAL(12,4),
    pnl_percent DECIMAL(8,4),
    status VARCHAR(20) DEFAULT 'OPEN', -- OPEN, CLOSED, CANCELLED
    strategy_used VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: ai_decisions
-- Records why the AI made each trading decision
CREATE TABLE IF NOT EXISTS trading_agent.ai_decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    decision_type VARCHAR(20) NOT NULL, -- ANALYSIS, TRADE, EXIT, HOLD
    decision VARCHAR(20) NOT NULL, -- BUY, SELL, HOLD
    confidence DECIMAL(3,2),
    reasoning TEXT,
    rules_applied INTEGER[],
    market_conditions JSONB,
    trade_id INTEGER, -- FK to trade_history
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: market_signals
-- Stores market data snapshots for analysis
CREATE TABLE IF NOT EXISTS trading_agent.market_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(10,4),
    volume BIGINT,
    bid DECIMAL(10,4),
    ask DECIMAL(10,4),
    high DECIMAL(10,4),
    low DECIMAL(10,4),
    open_price DECIMAL(10,4),
    close_price DECIMAL(10,4),
    indicators JSONB,
    signal_type VARCHAR(20), -- BULLISH, BEARISH, NEUTRAL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: course_content
-- Stores Warrior Trading course material
CREATE TABLE IF NOT EXISTS trading_agent.course_content (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    lesson_title VARCHAR(255),
    lesson_number INTEGER,
    content_type VARCHAR(50), -- transcript, pdf_text, notes, video_captions
    content TEXT,
    source_file VARCHAR(500),
    key_concepts TEXT[],
    processing_status VARCHAR(20) DEFAULT 'RAW', -- RAW, PROCESSED, INDEXED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: trading_sessions
-- Tracks trading session activity
CREATE TABLE IF NOT EXISTS trading_agent.trading_sessions (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(12,4) DEFAULT 0,
    win_rate DECIMAL(5,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trading_agent.trade_history(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trading_agent.trade_history(status);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol ON trading_agent.ai_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_market_signals_symbol ON trading_agent.market_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_course_content_processing ON trading_agent.course_content(processing_status);
CREATE INDEX IF NOT EXISTS idx_trading_rules_category ON trading_agent.trading_rules(category);

-- Grant permissions (adjust role as needed for your setup)
-- GRANT USAGE ON SCHEMA trading_agent TO ai_agent_dev;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA trading_agent TO ai_agent_dev;

COMMENT ON SCHEMA trading_agent IS 'AI Trading Agent - stores trading knowledge, decisions, and history';
