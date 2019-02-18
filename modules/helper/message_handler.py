# -*- coding: utf-8 -*-
import os
import threading

from modules.helper.functions import get_class_from_iname
from modules.helper.system import ROOT_PATH, THREADS
from modules.helper.module import MessagingModule


class MessageHandler(threading.Thread):
    def __init__(self, queue, process):
        self.queue = queue
        self.process = process
        threading.Thread.__init__(self)

    def run(self):
        while True:
            self.process(self.queue.get())


class Message(threading.Thread):
    def __init__(self, queue):
        super(self.__class__, self).__init__()
        # Creating dict for dynamic modules
        self.modules = []
        self.daemon = True
        self.queue = queue
        self.module_tag = "modules.messaging"
        self.threads = []

    def load_modules(self):
        modules_list = []
        modules_names = ["Webchat"]
        class_path = ROOT_PATH + "\\modules\\messaging\\" + modules_names[0]+".py"
        webchat = get_class_from_iname(class_path, modules_names[0])
        modules_list.append(webchat)
        self.modules.append(webchat())
        return modules_list

    def msg_process(self, message):
        # When we receive message we pass it via all loaded modules
        # All modules should return the message with modified/not modified
        #  content so it can be passed to new module, or to pass to CLI
        for m_module in self.modules:  # type: MessagingModule
            message = m_module.process_message(message, queue=self.queue)

    def run(self):
        for thread in range(THREADS):
            self.threads.append(MessageHandler(self.queue, self.msg_process))
            self.threads[thread].start()
