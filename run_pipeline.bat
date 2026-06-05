@echo off
REM =============================================================================
REM  Stock Calendar Pipeline - Batch Executor
REM  - 작업 스케줄러(Task Scheduler)에서 무인 실행용
REM  - pythonw.exe로 실행하여 콘솔 창 없이 백그라운드 동작
REM  - 로그 파일을 남겨 실행 내역 확인 가능
REM =============================================================================

REM Python 경로 (환경에 맞게 수정 가능)
set PYTHON_PATH=python

REM 실행 디렉토리
set BASE_DIR=C:\stock_calendar

REM 로그 파일 경로
set LOG_FILE=%BASE_DIR%\pipeline_log.txt

REM 현재 시간 기록
echo [%DATE% %TIME%] Pipeline started >> "%LOG_FILE%"

REM 파이프라인 실행 (--no-open 옵션으로 브라우저 열지 않음)
cd /d "%BASE_DIR%"
%PYTHON_PATH% run_pipeline.py --no-open >> "%LOG_FILE%" 2>&1

REM 완료 시간 기록
echo [%DATE% %TIME%] Pipeline finished (exit code: %ERRORLEVEL%) >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM 종료
exit /b %ERRORLEVEL%
