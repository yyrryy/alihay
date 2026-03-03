import os
from threading import Thread
from time import sleep
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        ip = "localhost"
        s.close() 
    return ip

ip = get_local_ip()
def runserver():
    os.system(f'python manage.py runserver {ip}:80')

def lunchchrome():
    sleep(2)  # wait for server
    os.system(f'start chrome http://{ip}')

t1 = Thread(target=runserver)
t2 = Thread(target=lunchchrome)

t1.start()
sleep(2)
t2.start()

