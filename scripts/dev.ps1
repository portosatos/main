# Start the whole stack in the foreground: postgres, mailpit, api, worker, frontend.
# Extra arguments go to `docker compose up`, e.g. scripts/dev.ps1 -d
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose up --build @args
exit $LASTEXITCODE
