CREATE TABLE phone_numbers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone_number TEXT UNIQUE NOT NULL,      -- E.164, e.g. +15551234567
  label TEXT,                             -- e.g. "me", "partner"
  verified INTEGER NOT NULL DEFAULT 0,    -- 0/1
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE otp_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone_number_id INTEGER NOT NULL REFERENCES phone_numbers(id),
  code_hash TEXT NOT NULL,                -- sha256 of the 6-digit code
  expires_at TIMESTAMP NOT NULL,
  used_at TIMESTAMP,                      -- NULL until consumed
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone_number_id INTEGER NOT NULL REFERENCES phone_numbers(id),
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  message_type TEXT NOT NULL CHECK (message_type IN ('otp', 'weather_request', 'weather_reply', 'other')),
  contents TEXT,
  parsed_lat REAL,
  parsed_lon REAL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
