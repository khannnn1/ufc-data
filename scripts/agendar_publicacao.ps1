# Agenda a publicação automática do site (src/publicar.py) no Agendador de Tarefas do Windows.
#
# Rode UMA vez, no PowerShell, a partir da pasta principal do projeto:
#   git fetch origin main
#   git worktree add -B publicacao ..\ufc-data-publicacao origin/main
#   powershell -ExecutionPolicy Bypass -File ..\ufc-data-publicacao\scripts\agendar_publicacao.ps1
#
# O que este script faz:
#   - na cópia de publicação (a pasta onde ele está), cria data\ como atalho (junção) para o data\ da
#     pasta principal: a base continua uma só;
#   - registra a tarefa "UFC Data - publicar", todo dia nos horários escolhidos (padrão 12:00 e 20:00), usando o
#     Python do venv da pasta principal. Se o PC estiver desligado no horário, roda assim que ligar.
#     O 2º horário é a repescagem: se a execução anterior do dia terminou sem erro, ele não faz nada.
# Rodar de novo (para mudar os horários):  ...\agendar_publicacao.ps1 -Horas 09:00,21:00
# Não se edita nada na cópia de publicação: a rotina descarta qualquer mudança nela a cada execução.
#
# Rodar agora:      Start-ScheduledTask -TaskName "UFC Data - publicar"
# Ver o resultado:  Get-Content <pasta principal>\data\publicacao.log -Tail 40
# Desligar:         Unregister-ScheduledTask -TaskName "UFC Data - publicar"

param(
    [string[]]$Horas = @("12:00", "20:00")
)
$ErrorActionPreference = "Stop"

$Copia = Split-Path -Parent $PSScriptRoot
$Principal = Split-Path -Parent (git -C $Copia rev-parse --path-format=absolute --git-common-dir)
if ((Resolve-Path $Copia).Path -eq (Resolve-Path $Principal).Path) {
    throw "Rode este script a partir da cópia de publicação (git worktree), não da pasta principal. Veja o topo do arquivo."
}

$Pythonw = Join-Path $Principal "venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) { throw "Não achei o venv em $Pythonw" }

$Dados = Join-Path $Copia "data"
if (-not (Test-Path $Dados)) {
    New-Item -ItemType Junction -Path $Dados -Target (Join-Path $Principal "data") | Out-Null
    Write-Host "data\ da cópia aponta para $(Join-Path $Principal 'data')"
}

$Acao = New-ScheduledTaskAction -Execute $Pythonw -Argument "-m src.publicar" -WorkingDirectory $Copia
$Gatilho = @($Horas | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ })
$Config = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "UFC Data - publicar" -Action $Acao -Trigger $Gatilho -Settings $Config `
    -Description "Coleta os eventos do UFC já encerrados e publica o site (src/publicar.py). Log: $Principal\data\publicacao.log" `
    -Force | Out-Null

Write-Host "Tarefa 'UFC Data - publicar' agendada para todo dia às $($Horas -join ' e ')."
Write-Host "Cópia de publicação: $Copia"
Write-Host "Log: $(Join-Path $Principal 'data\publicacao.log')"
