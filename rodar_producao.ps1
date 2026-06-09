Set-Location -LiteralPath "C:\Users\Administrador\OneDrive\Área de Trabalho\Mateus\Desenvolvimento\MAPA DE EMPRESAS"
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$logPath = Join-Path (Get-Location) ('producao_brasil_' + $ts + '.log')
Write-Output 'Log: ' + $logPath
python exportador_dados_serpro.py *> $logPath
