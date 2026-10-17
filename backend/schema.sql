-- Sequel Support HR desk. Local statutory record.
-- Bank numbers are not stored. Payroll keeps a submitted flag and last four digits.

CREATE TABLE homes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  region TEXT NOT NULL,
  sleep_in_rate NUMERIC(6, 2) NOT NULL
);

INSERT INTO homes (id, name, region, sleep_in_rate) VALUES
  ('mayfield', 'Mayfield Lodge', 'Bournemouth', 63.00),
  ('rainbow', 'Rainbow Lodge', 'Bournemouth', 63.00),
  ('fernleigh', 'Fernleigh House', 'Cornwall', 60.00);

CREATE TABLE candidates (
  id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  home_id TEXT REFERENCES homes (id),
  stage TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL,
  rejected_at TIMESTAMPTZ,
  on_reapply_watchlist BOOLEAN NOT NULL DEFAULT FALSE,
  completion_percent INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES candidates (id),
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  sha256 TEXT,
  dbs_checked_at TIMESTAMPTZ
);

CREATE TABLE employment_history (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES candidates (id),
  is_gap BOOLEAN NOT NULL DEFAULT FALSE,
  label TEXT NOT NULL,
  started_on TEXT,
  ended_on TEXT,
  gap_days INTEGER NOT NULL DEFAULT 0,
  explanation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE reference_checks (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES candidates (id),
  role TEXT NOT NULL,
  referee_name TEXT NOT NULL,
  dates_only BOOLEAN NOT NULL DEFAULT FALSE,
  verbal_on DATE,
  verbal_notes TEXT NOT NULL DEFAULT '',
  legitimate BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE interview_scores (
  candidate_id TEXT NOT NULL REFERENCES candidates (id),
  question_id INTEGER NOT NULL CHECK (question_id BETWEEN 1 AND 28),
  interviewer TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 5),
  PRIMARY KEY (candidate_id, question_id, interviewer)
);

CREATE TABLE medical_clearance (
  candidate_id TEXT PRIMARY KEY REFERENCES candidates (id),
  fit_for_shifts BOOLEAN,
  manual_handling BOOLEAN,
  personal_care BOOLEAN,
  adjustments_required BOOLEAN NOT NULL DEFAULT FALSE,
  adjustment_note TEXT NOT NULL DEFAULT '',
  referral_status TEXT NOT NULL DEFAULT 'not-required',
  cleared BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE payroll_handoff (
  candidate_id TEXT PRIMARY KEY REFERENCES candidates (id),
  bank_submitted BOOLEAN NOT NULL DEFAULT FALSE,
  account_last4 CHAR(4),
  p45_received BOOLEAN NOT NULL DEFAULT FALSE,
  starter_declaration BOOLEAN NOT NULL DEFAULT FALSE,
  emergency_name TEXT NOT NULL DEFAULT '',
  emergency_phone TEXT NOT NULL DEFAULT '',
  job_description_signed BOOLEAN NOT NULL DEFAULT FALSE,
  working_time_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
  key_phone_signed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  candidate_id TEXT,
  at TIMESTAMPTZ NOT NULL,
  actor TEXT NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL
);

CREATE TABLE ofsted_bundles (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES candidates (id),
  sha256 TEXT NOT NULL,
  watermark TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
