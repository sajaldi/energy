param (
    [string]$FilePath = "target_workflow.json"
)

$ApiKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
$BaseUrl = "http://localhost:5678/api/v1/workflows"

if (-not (Test-Path $FilePath)) {
    Write-Error "File not found: $FilePath"
    exit 1
}

$WorkflowJson = Get-Content $FilePath -Raw | ConvertFrom-Json

# Test creation (POST)
$BodyObj = [ordered]@{
    name = $WorkflowJson.name + " (TEST COPY)"
    nodes = $WorkflowJson.nodes
    connections = $WorkflowJson.connections
}

$Body = $BodyObj | ConvertTo-Json -Depth 100

$Headers = @{
    "X-N8N-API-KEY" = $ApiKey
    "Content-Type" = "application/json"
}

try {
    $Response = Invoke-RestMethod -Uri "$BaseUrl" -Method Post -Headers $Headers -Body $Body
    Write-Host "Success: Test workflow created."
    $Response | ConvertTo-Json -Depth 5
} catch {
    Write-Error "Failed to create workflow: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $reader.ReadToEnd()
        Write-Host "Response Body: $body"
    }
}
