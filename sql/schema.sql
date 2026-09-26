-- Esquema do banco SQLite (data/ufc.db), montado por src/banco.py a partir dos CSVs limpos.
-- Os CSVs têm uma linha por lutador em cada luta, com os dados da luta repetidos nas duas linhas;
-- aqui eles são separados em evento -> luta -> desempenho de cada lutador (-> por round).

DROP TABLE IF EXISTS desempenho_round;
DROP TABLE IF EXISTS desempenho;
DROP TABLE IF EXISTS lutas;
DROP TABLE IF EXISTS eventos;

CREATE TABLE eventos (
    evento_id   INTEGER PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    nome        TEXT NOT NULL
);

CREATE TABLE lutas (
    luta_id      INTEGER PRIMARY KEY,
    url          TEXT NOT NULL UNIQUE,
    evento_id    INTEGER NOT NULL REFERENCES eventos (evento_id),
    metodo       TEXT,              -- ex.: 'KO/TKO', 'Submission', 'Decision - Unanimous'
    round_final  INTEGER NOT NULL,
    tempo_final  TEXT NOT NULL,     -- 'M:SS' dentro do round final
    duracao_seg  INTEGER NOT NULL,  -- (round_final - 1) * 300 + tempo_final em segundos
    arbitro      TEXT
);

-- Uma linha por lutador em cada luta
CREATE TABLE desempenho (
    luta_id           INTEGER NOT NULL REFERENCES lutas (luta_id),
    lutador           TEXT    NOT NULL,
    resultado         TEXT    NOT NULL CHECK (resultado IN ('W', 'L', 'D', 'NC')),
    kd                INTEGER NOT NULL,  -- knockdowns
    sig_acertados     INTEGER NOT NULL,  -- golpes significativos
    sig_tentados      INTEGER NOT NULL,
    total_acertados   INTEGER NOT NULL,  -- todos os golpes
    total_tentados    INTEGER NOT NULL,
    quedas            INTEGER NOT NULL,
    quedas_tentadas   INTEGER NOT NULL,
    tent_finalizacao  INTEGER NOT NULL,
    reversoes         INTEGER NOT NULL,
    controle_seg      INTEGER,
    cabeca            INTEGER NOT NULL,  -- golpes significativos acertados por alvo...
    corpo             INTEGER NOT NULL,
    perna             INTEGER NOT NULL,
    distancia         INTEGER NOT NULL,  -- ...e por posição
    clinch            INTEGER NOT NULL,
    chao              INTEGER NOT NULL,
    PRIMARY KEY (luta_id, lutador)
);

-- Mesmas estatísticas, quebradas por round (sem resultado: ele é da luta, não do round)
CREATE TABLE desempenho_round (
    luta_id           INTEGER NOT NULL REFERENCES lutas (luta_id),
    lutador           TEXT    NOT NULL,
    round             INTEGER NOT NULL CHECK (round BETWEEN 1 AND 5),
    kd                INTEGER NOT NULL,
    sig_acertados     INTEGER NOT NULL,
    sig_tentados      INTEGER NOT NULL,
    total_acertados   INTEGER NOT NULL,
    total_tentados    INTEGER NOT NULL,
    quedas            INTEGER NOT NULL,
    quedas_tentadas   INTEGER NOT NULL,
    tent_finalizacao  INTEGER NOT NULL,
    reversoes         INTEGER NOT NULL,
    controle_seg      INTEGER,
    cabeca            INTEGER NOT NULL,
    corpo             INTEGER NOT NULL,
    perna             INTEGER NOT NULL,
    distancia         INTEGER NOT NULL,
    clinch            INTEGER NOT NULL,
    chao              INTEGER NOT NULL,
    PRIMARY KEY (luta_id, lutador, round),
    FOREIGN KEY (luta_id, lutador) REFERENCES desempenho (luta_id, lutador)
);

CREATE INDEX idx_lutas_evento ON lutas (evento_id);
CREATE INDEX idx_desempenho_lutador ON desempenho (lutador);
