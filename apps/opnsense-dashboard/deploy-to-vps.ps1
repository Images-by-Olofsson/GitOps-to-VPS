# OPNsense Dashboard - Deploy to VPS
# This script copies everything to your VPS and starts the Docker containers

$VPS_IP = "76.13.2.44"
$VPS_USER = "root"
$DEPLOY_PATH = "/root/opnsense-dashboard"

Write-Host "Deploying OPNsense Security Dashboard to VPS..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Copy dashboard files
Write-Host "Step 1: Copying dashboard files..." -ForegroundColor Yellow
if (Test-Path "dashboard") {
    Write-Host "   Dashboard directory found" -ForegroundColor Green
} else {
    Write-Host "   Creating dashboard directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "dashboard" -Force | Out-Null
    Write-Host "   Please copy your dashboard files (index.html, etc.) to ./dashboard/" -ForegroundColor Cyan
    Write-Host "   Press any key when ready..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Step 2: Create .env file
Write-Host ""
Write-Host "Step 2: Checking environment configuration..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Write-Host "   Creating .env file..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "   Please edit .env with your credentials:" -ForegroundColor Red
    Write-Host "      - OPNSENSE_API_KEY" -ForegroundColor Red
    Write-Host "      - OPNSENSE_API_SECRET" -ForegroundColor Red
    Write-Host "      - TAILSCALE_AUTHKEY" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Press any key when .env is configured..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Step 3: Copy to VPS
Write-Host ""
Write-Host "Step 3: Copying files to VPS ($VPS_IP)..." -ForegroundColor Yellow
Write-Host "   This will use SCP to copy all files..." -ForegroundColor Gray

$scpCommand = "scp -r . ${VPS_USER}@${VPS_IP}:${DEPLOY_PATH}"
Write-Host "   Running: $scpCommand" -ForegroundColor Gray
Invoke-Expression $scpCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Files copied successfully" -ForegroundColor Green
} else {
    Write-Host "   Failed to copy files" -ForegroundColor Red
    exit 1
}

# Step 4: Deploy on VPS
Write-Host ""
Write-Host "Step 4: Deploying on VPS..." -ForegroundColor Yellow

$sshCommand = @"
ssh ${VPS_USER}@${VPS_IP} 'cd ${DEPLOY_PATH} && chmod +x deploy.sh && ./deploy.sh'
"@

Write-Host "   Connecting to VPS and running deployment..." -ForegroundColor Gray
Invoke-Expression $sshCommand

# Step 5: Show results
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Your dashboard is now available at:" -ForegroundColor Yellow
Write-Host "   http://${VPS_IP}/opnsense-security/" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands on VPS:" -ForegroundColor Yellow
Write-Host "   ssh ${VPS_USER}@${VPS_IP}" -ForegroundColor Gray
Write-Host "   cd ${DEPLOY_PATH}" -ForegroundColor Gray
Write-Host "   docker-compose logs -f" -ForegroundColor Gray
Write-Host "   docker-compose restart" -ForegroundColor Gray
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "   1. Configure domain name (optional)" -ForegroundColor Gray
Write-Host "   2. Set up SSL with Let's Encrypt (optional)" -ForegroundColor Gray
Write-Host "   3. Configure Tailscale for secure OPNsense access" -ForegroundColor Gray
Write-Host ""
