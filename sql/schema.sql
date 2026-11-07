-- Esquema do banco SQLite (data/ufc.db), montado por src/banco.py a partir dos CSVs limpos.
-- Os CSVs têm uma linha por lutador em cada luta, com os dados da luta repetidos nas duas linhas;
-- aqui eles são separados em evento -> luta -> desempenho de cada lutador (-> por round).

DROP TABLE IF EXISTS desempenho_round;
DROP TABLE IF EXISTS desempenho;
DROP TABLE IF EXISTS lutas;
DROP TABLE IF EXISTS eventos;
DROP TABLE IF EXISTS lutadores;

-- evento_id em ordem cronológica inversa: 1 = evento mais recente
CREATE TABLE eventos (
    evento_id   INTEGER PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    nome        TEXT NOT NULL,
    data        TEXT NOT NULL CHECK (data GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')  -- 'AAAA-MM-DD'
);

CREATE TABLE lutas (
    luta_id      INTEGER PRIMARY KEY,
    url          TEXT NOT NULL UNIQUE,
    evento_id    INTEGER NOT NULL REFERENCES eventos (evento_id),
    metodo       TEXT,              -- ex.: 'KO/TKO', 'Submission', 'Decision - Unanimous'
    round_final  INTEGER NOT NULL,
    tempo_final  TEXT NOT NULL,     -- 'M:SS' dentro do round final
    duracao_seg  INTEGER NOT NULL,  -- rounds anteriores (pelo formato de tempo; 5 min se não houver) + tempo_final, em s
    arbitro      TEXT,
    categoria    TEXT,              -- categoria de peso, ex.: 'Lightweight', "Women's Flyweight", 'Catch Weight'
    disputa_titulo      INTEGER CHECK (disputa_titulo IN (0, 1)),       -- luta valendo cinturão
    bonus_luta          INTEGER CHECK (bonus_luta IN (0, 1)),           -- Luta da Noite
    bonus_performance   INTEGER CHECK (bonus_performance IN (0, 1))     -- Performance da Noite (do vencedor)
);

-- Dados de cada lutador (página dele no ufcstats); a url é o identificador único (nomes se repetem)
CREATE TABLE lutadores (
    url             TEXT PRIMARY KEY,
    nome            TEXT NOT NULL,
    altura_cm       REAL,
    envergadura_cm  REAL,
    base            TEXT,              -- 'Orthodox', 'Southpaw', 'Switch'...
    nascimento      TEXT               -- 'AAAA-MM-DD'
);

-- Uma linha por lutador em cada luta. Estatísticas NULL = não medidas: 21 lutas de 1994-1998
-- não têm estatísticas no ufcstats (NULL, não 0, para não puxar as médias para baixo)
CREATE TABLE desempenho (
    luta_id           INTEGER NOT NULL REFERENCES lutas (luta_id),
    lutador           TEXT    NOT NULL,
    lutador_url       TEXT    NOT NULL REFERENCES lutadores (url),
    resultado         TEXT    NOT NULL CHECK (resultado IN ('W', 'L', 'D', 'NC')),
    kd                INTEGER,  -- knockdowns
    sig_acertados     INTEGER,  -- golpes significativos
    sig_tentados      INTEGER,
    total_acertados   INTEGER,  -- todos os golpes
    total_tentados    INTEGER,
    quedas            INTEGER,
    quedas_tentadas   INTEGER,
    tent_finalizacao  INTEGER,
    reversoes         INTEGER,
    controle_seg      INTEGER,
    cabeca            INTEGER,  -- golpes significativos acertados por alvo...
    corpo             INTEGER,
    perna             INTEGER,
    distancia         INTEGER,  -- ...e por posição
    clinch            INTEGER,
    chao              INTEGER,
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
