param(
  [Parameter(Mandatory = $true)]
  [string]$RepoUrl,

  [string]$Branch = "main",

  [string]$SourceDir = "docs\interactive_map_public\static_site",

  [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$sourcePath = Resolve-Path (Join-Path $repoRoot $SourceDir)
$publishRoot = Join-Path $repoRoot "docs\joule_submission\github_pages_publish_worktree"
$resolvedRepoRoot = [System.IO.Path]::GetFullPath($repoRoot)
$resolvedPublishRoot = [System.IO.Path]::GetFullPath($publishRoot)

if (-not $resolvedPublishRoot.StartsWith($resolvedRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to prepare publish worktree outside repository: $resolvedPublishRoot"
}

if (Test-Path -LiteralPath $publishRoot) {
  Remove-Item -LiteralPath $publishRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $publishRoot | Out-Null

Copy-Item -Path (Join-Path $sourcePath "*") -Destination $publishRoot -Recurse -Force

Push-Location $publishRoot
try {
  git init
  git checkout -B $Branch
  git add -A
  git commit -m "Publish CO2 interactive map"
  git remote add origin $RepoUrl
  if ($Force) {
    git push -u origin $Branch --force
  } else {
    git push -u origin $Branch
  }
  Write-Output ""
  Write-Output "Published static site files to $RepoUrl on branch $Branch."
  Write-Output "Enable GitHub Pages: Settings -> Pages -> Deploy from a branch -> $Branch -> /root."
} finally {
  Pop-Location
}
