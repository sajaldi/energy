param (
    [string]$WorkflowId,
    [string]$FilePath = "target_workflow.json"
)

$ApiKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOTM0MjU4Ni1jN2MzLTQ2ZjEtYmE1Mi00MjE3OTBkYWU0ZmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjgzODliZjYtZGQxMC00NWIxLWI4ODAtZTJmMjA3ODIzNzhjIiwiaWF0IjoxNzczODQ1OTQ0fQ.13ueEws9HHdUdiO8ejyHSZsebjnuG_PSIzvmzcFzQrk"
$BaseUrl = "http://localhost:5678/api/v1/workflows"

if (-not (Test-Path $FilePath)) {
    Write-Error "File not found: $FilePath"
    exit 1
}

$WorkflowJson = Get-Content $FilePath -Raw | ConvertFrom-Json

# Construct the body with ONLY allowed fields
$BodyObj = [ordered]@{
    name = $WorkflowJson.name
    nodes = $WorkflowJson.nodes
    connections = $WorkflowJson.connections
}

if ($WorkflowJson.settings) { $BodyObj.Add("settings", $WorkflowJson.settings) }
if ($WorkflowJson.staticData) { $BodyObj.Add("staticData", $WorkflowJson.staticData) }
if ($WorkflowJson.meta) { $BodyObj.Add("meta", $WorkflowJson.meta) }

$Body = $BodyObj | ConvertTo-Json -Depth 100

$Headers = @{
    "X-N8N-API-KEY" = $ApiKey
    "Content-Type" = "application/json"
}

try {
    $Response = Invoke-RestMethod -Uri "$BaseUrl/$WorkflowId" -Method Put -Headers $Headers -Body $Body
    Write-Host "Success: Workflow updated."
    $Response | ConvertTo-Json -Depth 5
} catch {
    Write-Error "Failed to update workflow: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $body = $reader.ReadToEnd()
        Write-Host "Response Body: $body"
    }
}
