-- Consultas sobre data/ufc.db (esquema em sql/schema.sql). Cada uma responde à pergunta de um
-- gráfico do projeto; o notebook 03_sql.ipynb roda todas e confere com o resultado em Pandas.
-- Cada consulta começa com "-- nome: <identificador>", que o notebook usa para encontrá-la.


-- nome: metodos_vitoria
-- Como as lutas terminam? Uma linha por luta, então não há contagem dobrada.
SELECT
    metodo,
    COUNT(*)                                            AS lutas,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)  AS pct
FROM lutas
GROUP BY metodo
ORDER BY lutas DESC;


-- nome: vencedores_perdedores
-- O que separa quem vence de quem perde? Médias por luta de cada lado.
WITH medias AS (
    SELECT
        resultado,
        AVG(sig_acertados)            AS golpes_sig,
        AVG(quedas)                   AS quedas,
        AVG(controle_seg) / 60.0      AS controle_min,
        AVG(tent_finalizacao)         AS tent_finalizacao,
        AVG(kd)                       AS knockdowns
    FROM desempenho
    WHERE resultado IN ('W', 'L')
    GROUP BY resultado
)
SELECT
    ROUND(v.golpes_sig, 1)                         AS golpes_sig_v,
    ROUND(p.golpes_sig, 1)                         AS golpes_sig_p,
    ROUND(v.golpes_sig / p.golpes_sig, 1)          AS golpes_sig_razao,
    ROUND(v.quedas / p.quedas, 1)                  AS quedas_razao,
    ROUND(v.controle_min / p.controle_min, 1)      AS controle_razao,
    ROUND(v.tent_finalizacao / p.tent_finalizacao, 1) AS finalizacao_razao,
    ROUND(v.knockdowns / p.knockdowns, 1)          AS knockdowns_razao
FROM medias v
CROSS JOIN medias p
WHERE v.resultado = 'W' AND p.resultado = 'L';


-- nome: taxa_vitoria
-- Top 10 por taxa de vitória, com amostra mínima de 6 lutas (NC não entra na conta).
-- RANK() mostra os empates: vários invictos dividem a 1ª posição.
SELECT
    RANK() OVER (ORDER BY 1.0 * SUM(resultado = 'W') / COUNT(*) DESC) AS posicao,
    lutador,
    SUM(resultado = 'W')                                  AS vitorias,
    SUM(resultado = 'L')                                  AS derrotas,
    SUM(resultado = 'D')                                  AS empates,
    ROUND(100.0 * SUM(resultado = 'W') / COUNT(*), 1)     AS taxa_pct
FROM desempenho
WHERE resultado IN ('W', 'L', 'D')
GROUP BY lutador
HAVING COUNT(*) >= 6
ORDER BY taxa_pct DESC, vitorias DESC
LIMIT 10;


-- nome: precisao_quedas
-- Top 10 por precisão de quedas: pelo menos 15 tentativas E 3 lutas no período.
SELECT
    lutador,
    SUM(quedas)                                           AS conseguidas,
    SUM(quedas_tentadas)                                  AS tentadas,
    COUNT(*)                                              AS lutas,
    ROUND(100.0 * SUM(quedas) / SUM(quedas_tentadas), 1)  AS precisao_pct
FROM desempenho
GROUP BY lutador
HAVING SUM(quedas_tentadas) >= 15 AND COUNT(*) >= 3
ORDER BY precisao_pct DESC, conseguidas DESC
LIMIT 10;


-- nome: round_final_por_metodo
-- Em que round terminam nocautes e finalizações? Percentual dentro de cada método
-- (função de janela particionada por método). Rounds 4 e 5 agrupados.
WITH finalizadas AS (
    SELECT
        CASE
            WHEN metodo LIKE '%KO/TKO%' OR metodo LIKE 'TKO - Doctor%' THEN 'Nocaute'
            WHEN metodo LIKE '%Submission%' THEN 'Finalização'
        END AS tipo,
        CASE WHEN round_final >= 4 THEN '4º ou 5º' ELSE round_final || 'º' END AS round_grupo
    FROM lutas
)
SELECT
    tipo,
    round_grupo,
    COUNT(*)                                                               AS lutas,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY tipo), 1)    AS pct_do_metodo
FROM finalizadas
WHERE tipo IS NOT NULL
GROUP BY tipo, round_grupo
ORDER BY tipo DESC, round_grupo;


-- nome: origem_golpes
-- De onde saem os golpes de vencedores e perdedores (distância, clinch, chão)?
SELECT
    CASE resultado WHEN 'W' THEN 'Vencedores' ELSE 'Perdedores' END  AS grupo,
    ROUND(100.0 * SUM(distancia) / SUM(sig_acertados), 1)            AS distancia_pct,
    ROUND(100.0 * SUM(clinch)    / SUM(sig_acertados), 1)            AS clinch_pct,
    ROUND(100.0 * SUM(chao)      / SUM(sig_acertados), 1)            AS chao_pct
FROM desempenho
WHERE resultado IN ('W', 'L')
GROUP BY resultado
ORDER BY grupo DESC;


-- nome: volume_por_minuto
-- Quem mais arrisca golpes? Tentativas por minuto de luta (JOIN com lutas para a duração),
-- lutadores com pelo menos 4 lutas.
SELECT
    d.lutador,
    COUNT(*)                                                       AS lutas,
    ROUND(SUM(d.sig_tentados) / (SUM(l.duracao_seg) / 60.0), 1)    AS tentados_por_min,
    ROUND(100.0 * SUM(d.sig_acertados) / SUM(d.sig_tentados), 1)   AS precisao_pct
FROM desempenho AS d
JOIN lutas AS l USING (luta_id)
GROUP BY d.lutador
HAVING COUNT(*) >= 4
ORDER BY tentados_por_min DESC
LIMIT 10;


-- nome: arbitros
-- Os 10 árbitros com mais lutas e a % delas encerrada antes da decisão.
SELECT
    arbitro,
    COUNT(*)                                                                    AS lutas,
    ROUND(100.0 * SUM(metodo LIKE '%KO/TKO%' OR metodo LIKE 'TKO - Doctor%'
                      OR metodo LIKE '%Submission%') / COUNT(*), 1)             AS pct_antes_da_decisao
FROM lutas
GROUP BY arbitro
ORDER BY lutas DESC
LIMIT 10;


-- nome: golpes_por_round
-- Média de golpes significativos acertados por round (tende a subir por viés de sobrevivência:
-- só lutas longas chegam aos rounds finais).
SELECT
    round,
    COUNT(*)                     AS registros,
    ROUND(AVG(sig_acertados), 1) AS media_golpes_sig
FROM desempenho_round
GROUP BY round
ORDER BY round;


-- nome: destaque_por_evento
-- Em cada evento, quem acertou mais golpes significativos numa única luta?
-- ROW_NUMBER() por evento escolhe um só por evento; mostra os 10 maiores desses recordes.
WITH ranqueado AS (
    SELECT
        e.nome        AS evento,
        d.lutador,
        d.sig_acertados,
        ROW_NUMBER() OVER (PARTITION BY l.evento_id ORDER BY d.sig_acertados DESC, d.lutador) AS n
    FROM desempenho AS d
    JOIN lutas   AS l USING (luta_id)
    JOIN eventos AS e USING (evento_id)
)
SELECT evento, lutador, sig_acertados
FROM ranqueado
WHERE n = 1
ORDER BY sig_acertados DESC
LIMIT 10;


-- nome: sequencia_vitorias
-- Maior sequência de vitórias seguidas de cada lutador no período ("gaps and islands"):
-- a diferença entre dois ROW_NUMBER() é constante dentro de uma sequência de mesmo resultado.
-- As lutas de cada lutador são ordenadas pela data do evento.
WITH ordenado AS (
    SELECT
        d.lutador,
        d.resultado,
        ROW_NUMBER() OVER (PARTITION BY d.lutador ORDER BY e.data)
          - ROW_NUMBER() OVER (PARTITION BY d.lutador, d.resultado ORDER BY e.data) AS grupo
    FROM desempenho AS d
    JOIN lutas   AS l USING (luta_id)
    JOIN eventos AS e USING (evento_id)
),
sequencias AS (
    SELECT lutador, COUNT(*) AS vitorias_seguidas
    FROM ordenado
    WHERE resultado = 'W'
    GROUP BY lutador, grupo
)
SELECT lutador, MAX(vitorias_seguidas) AS maior_sequencia
FROM sequencias
GROUP BY lutador
ORDER BY maior_sequencia DESC, lutador
LIMIT 10;


-- nome: lutas_por_ano
-- Como as lutas terminam a cada ano do período (strftime extrai o ano da data do evento).
-- 2023 e o ano corrente são parciais: o recorte começa em abril de 2023.
SELECT
    strftime('%Y', e.data)                                                          AS ano,
    COUNT(DISTINCT e.evento_id)                                                     AS eventos,
    COUNT(*)                                                                        AS lutas,
    ROUND(100.0 * SUM(l.metodo LIKE '%KO/TKO%' OR l.metodo LIKE 'TKO - Doctor%') / COUNT(*), 1) AS nocaute_pct,
    ROUND(100.0 * SUM(l.metodo LIKE '%Submission%') / COUNT(*), 1)                  AS finalizacao_pct,
    ROUND(100.0 * SUM(l.metodo LIKE 'Decision%') / COUNT(*), 1)                     AS decisao_pct
FROM lutas AS l
JOIN eventos AS e USING (evento_id)
GROUP BY ano
ORDER BY ano;


-- nome: confronto_bases
-- Canhoto x ortodoxo: em lutas com vencedor entre bases diferentes, quantas o 1º lado venceu.
-- Self-join de desempenho (linha do vencedor com a do perdedor da mesma luta), cada uma ligada
-- à base do lutador em lutadores. Os confrontos são listados em VALUES para fixar a ordem e o lado.
WITH duelos AS (
    SELECT lv.base AS base_vencedor, lp.base AS base_perdedor
    FROM desempenho AS v
    JOIN desempenho AS p  ON p.luta_id = v.luta_id AND p.resultado = 'L'
    JOIN lutadores  AS lv ON lv.url = v.lutador_url
    JOIN lutadores  AS lp ON lp.url = p.lutador_url
    WHERE v.resultado = 'W' AND lv.base <> lp.base  -- base NULL fica de fora pela comparação
),
confrontos (ordem, lado_a, lado_b) AS (
    VALUES (1, 'Southpaw', 'Orthodox'), (2, 'Switch', 'Orthodox'), (3, 'Switch', 'Southpaw')
)
SELECT
    c.lado_a || ' x ' || c.lado_b                                         AS confronto,
    COUNT(*)                                                              AS lutas,
    SUM(d.base_vencedor = c.lado_a)                                       AS vitorias_lado_a,
    ROUND(100.0 * SUM(d.base_vencedor = c.lado_a) / COUNT(*), 1)          AS pct_lado_a
FROM confrontos AS c
JOIN duelos AS d
  ON (d.base_vencedor = c.lado_a AND d.base_perdedor = c.lado_b)
  OR (d.base_vencedor = c.lado_b AND d.base_perdedor = c.lado_a)
GROUP BY c.ordem, c.lado_a, c.lado_b
ORDER BY c.ordem;


-- nome: disputas_titulo
-- Disputas de cinturão x demais lutas. A CTE soma os dois lutadores de cada luta; o ritmo é por
-- minuto de luta e por lutador (duração x 2), porque as disputas têm 5 rounds e duram mais.
WITH por_luta AS (
    SELECT l.luta_id, l.disputa_titulo, l.duracao_seg, l.metodo, l.bonus_luta, l.bonus_performance,
           SUM(d.sig_acertados) AS golpes,
           SUM(d.kd)            AS kd
    FROM lutas AS l
    JOIN desempenho AS d USING (luta_id)
    GROUP BY l.luta_id
)
SELECT
    CASE disputa_titulo WHEN 1 THEN 'Disputa de cinturão' ELSE 'Demais lutas' END  AS tipo,
    COUNT(*)                                                                      AS lutas,
    ROUND(AVG(duracao_seg) / 60.0, 1)                                             AS duracao_min,
    ROUND(SUM(golpes) / (SUM(duracao_seg) / 60.0 * 2), 2)                         AS golpes_por_min,
    ROUND(SUM(kd) * 15 / (SUM(duracao_seg) / 60.0 * 2), 2)                        AS kd_por_15min,
    ROUND(100.0 * AVG(metodo LIKE '%KO/TKO%' OR metodo LIKE 'TKO - Doctor%'), 1)  AS nocaute_pct,
    ROUND(100.0 * AVG(metodo LIKE '%Submission%'), 1)                             AS finalizacao_pct,
    ROUND(100.0 * AVG(metodo LIKE 'Decision%'), 1)                                AS decisao_pct,
    ROUND(100.0 * AVG(bonus_luta), 1)                                             AS luta_da_noite_pct,
    ROUND(100.0 * AVG(bonus_performance), 1)                                      AS performance_pct
FROM por_luta
GROUP BY disputa_titulo
ORDER BY disputa_titulo DESC;
