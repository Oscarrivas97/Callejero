PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS hitos (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('VALID_ROUTE','FASTEST_ROUTE')),
    origin_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    destination_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    wording TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('EASY','MEDIUM','HARD')),
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A','B','C'))
);

CREATE TABLE IF NOT EXISTS question_options (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_letter TEXT NOT NULL CHECK (option_letter IN ('A','B','C')),
    route_text TEXT NOT NULL,
    route_json TEXT NOT NULL,
    PRIMARY KEY (question_id, option_letter)
);

CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(type);
