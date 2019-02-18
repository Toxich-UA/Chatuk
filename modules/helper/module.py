# -*- coding: utf-8 -*-
class BaseModule(object):
    def __init__(self, queue=None, category='main', *args, **kwargs):
        pass


class MessagingModule(BaseModule):
    def __init__(self, *args, **kwargs):
        BaseModule.__init__(self, *args, **kwargs)
        self._category = 'messaging'

    def process_message(self, message, queue=None):
        """

        :param message: Received Message class
        :type message: TextMessage
        :param queue: Main queue
        :type queue: Queue.Queue
        :return: Message Class, could be None if message is "cleared"
        :rtype: Message
        """
        return message
