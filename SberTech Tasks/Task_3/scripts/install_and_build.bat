@echo off
setlocal enabledelayedexpansion
set IMAGE=secmem-agent

:: Build Docker image
docker build -t %IMAGE% . || exit /b 1

:: Run tests inside container
docker run --rm %IMAGE% || exit /b 1

echo Done.