@echo off
title CBT Interface (close this window to stop)
cd /d "%~dp0"
set PYCMD=
where py >nul 2>nul && set PYCMD=py
if not defined PYCMD where python >nul 2>nul && set PYCMD=python
if not defined PYCMD (
  echo Python was not found on this PC.
  echo Install it from python.org and tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
%PYCMD% cbt_server.py
if errorlevel 1 pause
