param(
    [switch]$ReplayOnly,
    [int]$Seconds = 30,
    [string]$CaptureDirectory = ''
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Image = 'ahmet-fprime-telemetry-lab:20261021'
$LogRoot = Join-Path $Root 'outputs/runner'
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

function Invoke-LabStep {
    param([string]$Label, [string]$Executable, [string[]]$StepArguments, [int[]]$AcceptedCodes = @(0))
    $LogPath = Join-Path $LogRoot ($Label + '.log')
    $PriorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Executable @StepArguments *> $LogPath
    $StepExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PriorPreference
    if ($StepExitCode -notin $AcceptedCodes) {
        Get-Content -LiteralPath $LogPath -Tail 18 | Write-Host
        throw "$Label failed (exit $StepExitCode). See $LogPath"
    }
    Write-Host "[$Label] completed"
}

function Invoke-LabContainer {
    param([string]$Label, [string[]]$ContainerArguments)
    Invoke-LabStep -Label $Label -Executable 'docker' -StepArguments (@(
        'run', '--rm', '--mount', "type=bind,source=$Root,target=/work", $Image
    ) + $ContainerArguments)
}

Push-Location $Root
try {
    Invoke-LabStep -Label 'docker-ready' -Executable 'docker' -StepArguments @('info', '--format', '{{.ServerVersion}}')
    if (-not (Test-Path 'vendor/fprime/AGENTS.md')) {
        Invoke-LabStep -Label 'sources' -Executable 'python' -StepArguments @('scripts/bootstrap_sources.py')
    }
    $env:GOROOT = ''
    $GoExe = (& python scripts/bootstrap_go.py | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Go setup failed' }
    $env:GOROOT = Split-Path (Split-Path $GoExe -Parent) -Parent
    $env:GOPATH = Join-Path $Root 'tools/go_path'
    $env:GOCACHE = Join-Path $Root 'tools/go_cache'
    $env:GOTMPDIR = Join-Path $Root 'tools/go_tmp'
    New-Item -ItemType Directory -Path $env:GOTMPDIR -Force | Out-Null
    $env:CGO_ENABLED = '0'; $env:GOENV = 'off'; $env:GOTOOLCHAIN = 'local'
    $ErrorActionPreference = 'Continue'
    docker image inspect $Image *> (Join-Path $LogRoot 'image-inspect.json')
    $ImageExists = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    if (-not $ImageExists) {
        Invoke-LabStep -Label 'image-build' -Executable 'docker' -StepArguments @('build', '-t', $Image, '.')
    }
    if (-not $ReplayOnly) {
        Invoke-LabStep -Label 'configure' -Executable 'python' -StepArguments @('scripts/configure_sender.py')
        $ContainerBuildDir = '/work/vendor/fprime/TestDeploymentsProject/Ref'
        if (-not (Test-Path 'vendor/fprime/TestDeploymentsProject/build-fprime-automatic-native/CMakeCache.txt')) {
            Invoke-LabStep -Label 'sender-generate' -Executable 'docker' -StepArguments @(
                'run','--rm','--mount',"type=bind,source=$Root,target=/work",'-w',$ContainerBuildDir,$Image,'fprime-util','generate')
        }
        Invoke-LabStep -Label 'sender-build' -Executable 'docker' -StepArguments @(
            'run','--rm','--mount',"type=bind,source=$Root,target=/work",'-w',$ContainerBuildDir,$Image,'fprime-util','build','-j','6')
        if ($CaptureDirectory -eq '') { $CaptureDirectory = 'outputs/run_' + (Get-Date -Format 'yyyyMMdd_HHmmss') }
        Invoke-LabContainer -Label 'capture' -ContainerArguments @(
            'python','/work/scripts/capture_sender.py','--seconds',"$Seconds",'--file-bytes','8192','--output',"/work/$CaptureDirectory")
    } elseif ($CaptureDirectory -eq '') { $CaptureDirectory = 'outputs/live_file_transfer' }
    if (-not (Test-Path "$CaptureDirectory/downlink.bin")) { throw 'No capture exists for replay' }
    $Dictionary = 'vendor/fprime/TestDeploymentsProject/build-fprime-automatic-native/Ref/Top/Ref_RefSystemDictionary.json'
    if ($ReplayOnly) { $Dictionary = 'data/fprime-system-dictionary.json' }
    Invoke-LabStep -Label 'dictionary-conversion' -Executable 'python' -StepArguments @(
        'scripts/convert_dictionary.py',$Dictionary,'build/hermes-dictionary.json')
    Push-Location receiver
    try {
        Invoke-LabStep -Label 'go-dependencies' -Executable $GoExe -StepArguments @('mod','download')
        Invoke-LabStep -Label 'receiver-tests' -Executable $GoExe -StepArguments @('test','-v','.')
        Invoke-LabStep -Label 'receiver-build' -Executable $GoExe -StepArguments @('build','-o','../build/lab-receiver.exe','.')
    } finally { Pop-Location }
    $Receiver = Join-Path $Root 'build/lab-receiver.exe'
    Invoke-LabStep -Label 'hermes-decode' -Executable $Receiver -StepArguments @(
        '--dictionary','build/hermes-dictionary.json','--input',"$CaptureDirectory/downlink.bin",
        '--output',"$CaptureDirectory/hermes.jsonl",'--stats',"$CaptureDirectory/hermes-stats.json")
    Invoke-LabContainer -Label 'gds-decode' -ContainerArguments @(
        'python','/work/scripts/decode_gds.py','--dictionary',"/work/$Dictionary",'--input',"/work/$CaptureDirectory/downlink.bin",
        '--output',"/work/$CaptureDirectory/gds.jsonl",'--stats',"/work/$CaptureDirectory/gds-stats.json")
    Invoke-LabStep -Label 'compare' -Executable 'python' -StepArguments @(
        'scripts/compare_results.py','--hermes',"$CaptureDirectory/hermes.jsonl",'--gds',"$CaptureDirectory/gds.jsonl",
        '--expected-file',"$CaptureDirectory/payload.dat",'--output',"$CaptureDirectory/comparison.json")
    Invoke-LabStep -Label 'original-hermes' -Executable $Receiver -StepArguments @(
        '--original','--dictionary','build/hermes-dictionary.json','--input',"$CaptureDirectory/downlink.bin",
        '--output',"$CaptureDirectory/original-hermes.jsonl",'--stats',"$CaptureDirectory/original-hermes-stats.json")
    Invoke-LabStep -Label 'compare-original' -Executable 'python' -AcceptedCodes @(0,1) -StepArguments @(
        'scripts/compare_results.py','--hermes',"$CaptureDirectory/original-hermes.jsonl",'--gds',"$CaptureDirectory/gds.jsonl",
        '--expected-file',"$CaptureDirectory/payload.dat",'--output',"$CaptureDirectory/original-hermes-comparison.json")
    $FaultDir = "$CaptureDirectory/faults"
    Invoke-LabStep -Label 'fault-fixtures' -Executable 'python' -StepArguments @('scripts/inject_faults.py',"$CaptureDirectory/downlink.bin",$FaultDir)
    foreach ($Case in @('drop_continuation_frame','crc_error_continuation_frame')) {
        Invoke-LabStep -Label "$Case-hermes" -Executable $Receiver -StepArguments @(
            '--dictionary','build/hermes-dictionary.json','--input',"$FaultDir/$Case.bin",
            '--output',"$FaultDir/$Case-hermes.jsonl",'--stats',"$FaultDir/$Case-hermes-stats.json")
        Invoke-LabContainer -Label "$Case-gds" -ContainerArguments @(
            'python','/work/scripts/decode_gds.py','--dictionary',"/work/$Dictionary",'--input',"/work/$FaultDir/$Case.bin",
            '--output',"/work/$FaultDir/$Case-gds.jsonl",'--stats',"/work/$FaultDir/$Case-gds-stats.json")
        Invoke-LabStep -Label "$Case-compare" -Executable 'python' -StepArguments @(
            'scripts/compare_results.py','--hermes',"$FaultDir/$Case-hermes.jsonl",'--gds',"$FaultDir/$Case-gds.jsonl",
            '--reference',"$CaptureDirectory/hermes.jsonl",'--output',"$FaultDir/$Case-comparison.json")
    }
    Invoke-LabStep -Label 'report' -Executable 'python' -StepArguments @('scripts/write_run_summary.py',$CaptureDirectory)
    Write-Host "Completed. Read $CaptureDirectory/REPORT.md"
} finally { Pop-Location }
