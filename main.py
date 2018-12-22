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


lock = Lock()

def animation():
    touchphat.all_off()
    for i in range(1, 7):
        touchphat.led_on(i)
        time.sleep(0.05)
    for i in range(1, 7):
        touchphat.led_off(i)
        time.sleep(0.05)

def blink(key):
    touchphat.all_off()
    for i in range(0, 3):
        touchphat.led_off(key)
        time.sleep(0.1)
        touchphat.led_on(key)
        time.sleep(0.1)
    touchphat.all_off()


@touchphat.on_release(['Back','A', 'B', 'C', 'D','Enter'])
def handle_touch(event):
    with lock:
        try:
            client.publish(
                    TOPIC,
                    event.name,
                    1
                )
            blink(event.name)
        except AWSIoTExceptions.publishTimeoutException:
            pass


def cb(client, userdata, message):
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

    client = AWSIoTMQTTClient(THING_NAME)
    client.configureEndpoint(ENDPOINT, 8883)
    client.configureCredentials(ROOTCA, PRIVATE, CERT)

    client.configureAutoReconnectBackoffTime(1, 32, 20)
    client.configureOfflinePublishQueueing(-1)
    client.configureDrainingFrequency(2)
    client.configureConnectDisconnectTimeout(300)
    client.configureMQTTOperationTimeout(1)

    client.subscribe('$aws/things/'+THING_NAME+'/shadow/update/delta', 1, cb)
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
