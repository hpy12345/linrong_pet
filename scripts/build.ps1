param(
    [switch]$SkipTests,
    [switch]$SkipRuntimeSmoke,
    [switch]$SkipInstaller,
    [switch]$RegenerateVoice
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

function Remove-SafeBuildDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $ResolvedRoot = [IO.Path]::GetFullPath($Root)
    $ResolvedPath = [IO.Path]::GetFullPath($Path)
    if (-not $ResolvedPath.StartsWith($ResolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the workspace: $ResolvedPath"
    }
    if (Test-Path -LiteralPath $ResolvedPath) {
        Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
    }
}

function Assert-LastExitCode {
    param([Parameter(Mandatory = $true)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $Python)) {
    uv venv --python 3.12 (Join-Path $Root ".venv")
    Assert-LastExitCode "Creating the Python environment"
}

uv pip install --python $Python -e "${Root}[build,test]"
Assert-LastExitCode "Installing build dependencies"

if ($RegenerateVoice) {
    & $Python (Join-Path $Root "scripts\generate_voice.py") `
        --output-dir (Join-Path $Root "src\linrong_pet\assets\audio")
    Assert-LastExitCode "Generating offline neural voice assets"
}

& $Python (Join-Path $Root "scripts\validate_voice.py") `
    --audio-dir (Join-Path $Root "src\linrong_pet\assets\audio")
Assert-LastExitCode "Validating offline voice assets"

& $Python (Join-Path $Root "scripts\validate_assets.py") `
    --animation (Join-Path $Root "src\linrong_pet\assets\animation.json") `
    --spritesheet (Join-Path $Root "src\linrong_pet\assets\spritesheet.webp")
Assert-LastExitCode "Validating sprite assets"

& $Python (Join-Path $Root "scripts\generate_icon.py") `
    --animation (Join-Path $Root "src\linrong_pet\assets\animation.json") `
    --spritesheet (Join-Path $Root "src\linrong_pet\assets\spritesheet.webp") `
    --output (Join-Path $Root "src\linrong_pet\assets\linrong.ico")
Assert-LastExitCode "Generating the application icon"

& $Python (Join-Path $Root "scripts\export_runtime_frames.py") `
    --animation (Join-Path $Root "src\linrong_pet\assets\animation.json") `
    --spritesheet (Join-Path $Root "src\linrong_pet\assets\spritesheet.webp") `
    --output-dir (Join-Path $Root "src\linrong_pet\assets\frames")
Assert-LastExitCode "Exporting memory-efficient runtime frames"

& $Python (Join-Path $Root "scripts\render_animation_qa.py") `
    --animation (Join-Path $Root "src\linrong_pet\assets\animation.json") `
    --spritesheet (Join-Path $Root "src\linrong_pet\assets\spritesheet.webp") `
    --output-dir (Join-Path $Root "build\qa\previews-v1.3")
Assert-LastExitCode "Rendering animation QA previews"

if (-not $SkipTests) {
    & $Python -m pytest
    Assert-LastExitCode "Running tests"
}

Remove-SafeBuildDirectory (Join-Path $Root "build\pyinstaller")
Remove-SafeBuildDirectory (Join-Path $Root "dist\LinRongPet")
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath (Join-Path $Root "build\pyinstaller") `
    --distpath (Join-Path $Root "dist") `
    (Join-Path $Root "LinRongPet.spec")
Assert-LastExitCode "Building the PyInstaller application"

if (-not $SkipRuntimeSmoke) {
    & $Python (Join-Path $Root "scripts\runtime_smoke.py") `
        (Join-Path $Root "dist\LinRongPet\LinRongPet.exe") `
        --json-out (Join-Path $Root "build\qa\runtime-smoke.json")
    Assert-LastExitCode "Running the packaged application smoke test"
}

if (-not $SkipInstaller) {
    $IsccCommand = Get-Command iscc -ErrorAction SilentlyContinue
    $IsccPath = if ($IsccCommand) { $IsccCommand.Source } else { $null }
    if (-not $IsccPath) {
        $Candidate = "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
        if (Test-Path $Candidate) {
            $IsccPath = $Candidate
        }
    }
    if (-not $IsccPath) {
        throw "Inno Setup 6 compiler (ISCC.exe) was not found."
    }
    & $IsccPath (Join-Path $Root "installer\LinRongPet.iss")
    Assert-LastExitCode "Building the Inno Setup installer"
}
