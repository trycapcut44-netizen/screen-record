@echo off
title ZoomRecorder Pro - License Key Generator
python generate_key.py
if errorlevel 1 (
    echo.
    echo Python not found in path. Please run with Python.
    pause
)
