import os
from threading import Thread
from time import sleep
import subprocess
import sys

def runserver():
    os.system('python manage.py runserver localhost:8000')

def lunchchrome():
    # ensure the django server is up and running
    sleep(2)
    # get ipv4 address
    os.system('start chrome http://localhost:8000')
t1=Thread(target=runserver)

t2=Thread(target=lunchchrome)

t1.start()
sleep(2)
t2.start()