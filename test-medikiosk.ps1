# =====================================
# MediKiosk Backend Smoke Test
# =====================================

$BASE = "http://localhost:8000"

Write-Host "`n===== HEALTH ====="
$health = Invoke-RestMethod `
    -Uri "$BASE/api/health" `
    -Method GET
$health | ConvertTo-Json -Depth 10

Write-Host "`n===== CREATE SESSION ====="

$sessionBody = @{
    patient_name = "Test Patient"
    age = 30
    gender = "female"
} | ConvertTo-Json

try {
    $session = Invoke-RestMethod `
        -Uri "$BASE/api/sessions" `
        -Method POST `
        -ContentType "application/json" `
        -Body $sessionBody

    $session | ConvertTo-Json -Depth 10

    $sessionId = $session.id

    if (-not $sessionId) {
        $sessionId = $session.session_id
    }

    Write-Host "Session ID: $sessionId"
}
catch {
    Write-Host "Create session failed:"
    $_
}

if ($sessionId) {

    Write-Host "`n===== GET SESSION ====="

    Invoke-RestMethod `
        -Uri "$BASE/api/sessions/$sessionId" `
        -Method GET |
        ConvertTo-Json -Depth 10

    Write-Host "`n===== CONSENT ====="

    $consentBody = @{
        consent_given = $true
    } | ConvertTo-Json

    try {
        Invoke-RestMethod `
            -Uri "$BASE/api/sessions/$sessionId/consent" `
            -Method POST `
            -ContentType "application/json" `
            -Body $consentBody |
            ConvertTo-Json -Depth 10
    }
    catch {
        Write-Host $_
    }

    Write-Host "`n===== NEXT QUESTION ====="

    try {
        $question = Invoke-RestMethod `
            -Uri "$BASE/api/interview/$sessionId/next" `
            -Method GET

        $question | ConvertTo-Json -Depth 10

        $questionId = $question.question_id

        if ($questionId) {

            Write-Host "`n===== ANSWER QUESTION ====="

            $answerBody = @{
                question_id = $questionId
                answer = "Test answer"
            } | ConvertTo-Json

            Invoke-RestMethod `
                -Uri "$BASE/api/interview/$sessionId/answer" `
                -Method POST `
                -ContentType "application/json" `
                -Body $answerBody |
                ConvertTo-Json -Depth 10
        }
    }
    catch {
        Write-Host $_
    }
}

Write-Host "`n===== LIST SESSIONS ====="

try {
    Invoke-RestMethod `
        -Uri "$BASE/api/sessions" `
        -Method GET |
        ConvertTo-Json -Depth 10
}
catch {
    Write-Host $_
}

Write-Host "`n===== LLM EXTRACTION ====="

$extractBody = @{
    text = "Patient has fever for 3 days and cough."
} | ConvertTo-Json

try {
    Invoke-RestMethod `
        -Uri "$BASE/api/llm/extract" `
        -Method POST `
        -ContentType "application/json" `
        -Body $extractBody |
        ConvertTo-Json -Depth 20
}
catch {
    Write-Host $_
}

Write-Host "`n===== ACTIVE TRIAGE ====="

try {
    Invoke-RestMethod `
        -Uri "$BASE/api/triage/active" `
        -Method GET |
        ConvertTo-Json -Depth 10
}
catch {
    Write-Host $_
}

Write-Host "`n===== CASES ====="

try {
    $cases = Invoke-RestMethod `
        -Uri "$BASE/api/cases" `
        -Method GET

    $cases | ConvertTo-Json -Depth 10
}
catch {
    Write-Host $_
}

Write-Host "`n===== SPEECH SYNTHESIZE ====="

$speechBody = @{
    text = "Hello from MediKiosk"
} | ConvertTo-Json

try {
    Invoke-RestMethod `
        -Uri "$BASE/api/speech/synthesize" `
        -Method POST `
        -ContentType "application/json" `
        -Body $speechBody |
        ConvertTo-Json -Depth 10
}
catch {
    Write-Host $_
}

Write-Host "`n===== DONE ====="