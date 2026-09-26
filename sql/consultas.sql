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
-- A ordem das lutas vem do evento: evento_id segue a ordem da coleta (1 = mais recente).
WITH ordenado AS (
    SELECT
        d.lutador,
        d.resultado,
        ROW_NUMBER() OVER (PARTITION BY d.lutador ORDER BY l.evento_id DESC)
          - ROW_NUMBER() OVER (PARTITION BY d.lutador, d.resultado ORDER BY l.evento_id DESC) AS grupo
    FROM desempenho AS d
    JOIN lutas AS l USING (luta_id)
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
