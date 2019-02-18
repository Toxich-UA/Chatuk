# -*- coding: utf-8 -*-
from time import sleep

import config
from modules.chat.twitch import *
from modules.helper.message_handler import Message


def main():
    queue = Queue.Queue()

    channels = {"chistor_", "thijs", "silvername"}
    #channels = {"chistor_"}
    #channels = ["toxich_ua"]
    for channel in channels:
        TWChannel(queue, config.HOST, config.PORT, channel, True).start()

    # Creating queues for messaging transfer between chat threads
    # Loading module for message processing...
    msg = Message(queue)
    loaded_modules = msg.load_modules()
    loaded_modules[0]().load_module()
    msg.start()

    while True:
        sleep(1)


if __name__ == '__main__':
    main()
