#!/usr/bin/env python3
# coding: utf-8

from logging import getLogger
logger = getLogger('kishinami')

import time
import datetime
import os
import sys
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception import AWSIoTExceptions
import json
import touchphat
from threading import Lock

CHECK_SPAN = 10
THING_NAME = 'kishinami'
ENDPOINT = 'a3gt2cb172okvl-ats.iot.ap-northeast-1.amazonaws.com'
ROOTCA = '/home/pi/AmazonRootCA1.pem'
PRIVATE = '/home/pi/e15c31a340-private.pem.key'
CERT = '/home/pi/e15c31a340-certificate.pem.crt'
TOPIC = 'button/'+THING_NAME+'/release'

MODE = 'add'

lock = Lock()

def mode_change(mode='add'):
    global MODE
    if mode == 'add':
        MODE = 'add'
        touchphat.all_off()
        touchphat.led_on('Enter')
    elif mode == 'remove':
        MODE = 'remove'
        touchphat.all_off()
        touchphat.led_on('Back')


def animation():
    touchphat.all_off()
    for i in range(1, 7):
        touchphat.led_on(i)
        time.sleep(0.05)
    for i in range(1, 7):
        touchphat.led_off(i)
        time.sleep(0.05)

def blink(key):
    touchphat.led_off('A')
    touchphat.led_off('B')
    touchphat.led_off('C')
    touchphat.led_off('D')
    for i in range(0, 3):
        touchphat.led_off(key)
        time.sleep(0.1)
        touchphat.led_on(key)
        time.sleep(0.1)
    touchphat.led_off('A')
    touchphat.led_off('B')
    touchphat.led_off('C')
    touchphat.led_off('D')

@touchphat.on_release(['Back', 'Enter'])
def handle_mode(event):
    with lock:
        try:
            mode = 'add' if event.name == 'Enter' else 'remove'
            mode_change(mode)
            client.publish(
                    TOPIC,
                    json.dumps({
                        "name": THING_NAME,
                        "state": "modechange",
                        "button": event.name,
                        "mode": MODE
                    }),
                    1
                )
        except AWSIoTExceptions.publishTimeoutException:
            pass
    

@touchphat.on_release(['A', 'B', 'C', 'D'])
def handle_touch(event):
    with lock:
        try:
            client.publish(
                    TOPIC,
                    json.dumps({
                        "name": THING_NAME,
                        "state": "keypress",
                        "mode": MODE,
                        "button": event.name
                    }),
                    1
                )
            blink(event.name)
        except AWSIoTExceptions.publishTimeoutException:
            pass


def cb(client, userdata, message):
    if message.topic == '$aws/things/'+THING_NAME+'/shadow/update/delta':
        delta_function(client, userdata, message)
    elif message.topic == 'cmnd/'+THING_NAME+'/result':
        result_function(client, userdata, message)


def result_function(client, userdata, message):
    r = json.loads(message.payload.decode('utf-8'))
    print(r)


def delta_function(client, userdata, message):
    r = json.loads(message.payload.decode('utf-8'))

    try:
        global CHECK_SPAN
        CHECK_SPAN = int(r['state']['check_span'])
    except KeyError:
        pass


if __name__ == '__main__':
    from logging import StreamHandler, DEBUG
    logger.setLevel(DEBUG)
    logger.addHandler(StreamHandler(stream=sys.stdout))

    animation()
    mode_change('add')

    client = AWSIoTMQTTClient(THING_NAME)
    client.configureEndpoint(ENDPOINT, 8883)
    client.configureCredentials(ROOTCA, PRIVATE, CERT)

    client.configureAutoReconnectBackoffTime(1, 32, 20)
    client.configureOfflinePublishQueueing(-1)
    client.configureDrainingFrequency(2)
    client.configureConnectDisconnectTimeout(300)
    client.configureMQTTOperationTimeout(1)

    client.subscribe('$aws/things/'+THING_NAME+'/shadow/update/delta', 1, cb)
    client.subscribe('cmnd/'+THING_NAME+'/#', 1, cb)
    client.connect(60)

    while True:
        try:
            shadow = {
                "state": {
                    "reported": {
                        "date": time.time(),
                        "check_span": CHECK_SPAN
                    }
                }
            }

            client.publish('$aws/things/'+THING_NAME+'/shadow/update', json.dumps(shadow), 1)

        except AWSIoTExceptions.publishTimeoutException:
            time.sleep(CHECK_SPAN)
            continue

        except Exception as e:
            logger.exception(e)

        time.sleep(CHECK_SPAN)
