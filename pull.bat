@echo off
REM Pull the latest code from GitHub
git pull origin main

REM Run Django migrations
py manage.py makemigrations
py manage.py migrate