# -*- coding: utf-8 -*-
import json
import logging
import os
import socket
import threading

from cherrypy.lib.static import serve_file
from ws4py.websocket import WebSocket

import queue
import cherrypy

from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from modules.helper.system import THREADS

from modules.helper.module import MessagingModule
from modules.helper.system import ROOT_PATH, SRC_PATH
from ws4py.websocket import EchoWebSocket

s_queue = queue.Queue()
log = logging.getLogger('webchat')
WS_THREADS = THREADS + 1
REMOVED_TRIGGER = '%%REMOVED%%'
EMOTE_FORMAT = u':emote;{0}:'
HISTORY_SIZE = 50


def process_emotes(emotes):
    return [{'id': EMOTE_FORMAT.format(emote.id), 'url': emote.url} for emote in emotes]


def process_platform(platform):
    return {'id': platform.id, 'icon': platform.icon}


def process_badges(badges):
    return [{'badge': badge.id, 'url': badge.url} for badge in badges]


def prepare_message(message):
    payload = message['payload']

    if message['type'] == 'command':
        log.info("Command cached: {}".format(message['text']))
        return message

    if 'emotes' in payload and payload['emotes']:
        payload['emotes'] = process_emotes(payload['emotes'])

    if 'badges' in payload:
        payload['badges'] = process_badges(payload['badges'])

    if 'platform' in payload:
        payload['platform'] = process_platform(payload['platform'])

    return message


class MessagingThread(threading.Thread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.running = True

    def run(self):
        while self.running:
            message = s_queue.get()

            if isinstance(message, dict):
                raise Exception("Got dict message {}".format(message))

            self.send_message(message, 'chat')
        log.info("Messaging thread stopping")

    def stop(self):
        self.running = False

    def send_message(self, message, chat_type):
        send_message = prepare_message(message.json())
        ws_list = cherrypy.engine.publish('get-clients', chat_type)[0]
        for ws in ws_list:
            try:
                ws.send(json.dumps(send_message))
            except Exception as exc:
                log.exception(exc)
                log.info(send_message)


class WebChatSocketServer(WebSocket):
    def __init__(self, sock, protocols=None, extensions=None, environ=None, heartbeat_freq=None):
        WebSocket.__init__(self, sock)
        self.daemon = True
        self.clients = []
        self.type = 'chat'

    def opened(self):
        cherrypy.engine.publish('add-client', self.peer_address, self)

    def closed(self, code, reason=None):
        cherrypy.engine.publish('del-client', self.peer_address, self)


class WebChatPlugin(WebSocketPlugin):
    def __init__(self, bus):
        WebSocketPlugin.__init__(self, bus)
        self.daemon = True
        self.clients = []
        self.history = []
        self.history_size = HISTORY_SIZE

    def start(self):
        WebSocketPlugin.start(self)
        self.bus.subscribe('add-client', self.add_client)
        self.bus.subscribe('del-client', self.del_client)
        self.bus.subscribe('get-clients', self.get_clients)
        self.bus.subscribe('add-history', self.add_history)
        self.bus.subscribe('get-history', self.get_history)
        self.bus.subscribe('del-history', self.del_history)
        self.bus.subscribe('process-command', self.process_command)

    def stop(self):
        WebSocketPlugin.stop(self)
        self.bus.unsubscribe('add-client', self.add_client)
        self.bus.unsubscribe('del-client', self.del_client)
        self.bus.unsubscribe('get-clients', self.get_clients)
        self.bus.unsubscribe('add-history', self.add_history)
        self.bus.unsubscribe('get-history', self.get_history)
        self.bus.unsubscribe('process-command', self.process_command)

    def add_client(self, addr, websocket):
        self.clients.append({'ip': addr[0], 'port': addr[1], 'websocket': websocket})

    def del_client(self, addr, websocket):
        try:
            self.clients.remove({'ip': addr[0], 'port': addr[1], 'websocket': websocket})
        except Exception as exc:
            log.exception("Exception %s", exc)
            log.info('Unable to delete client %s', addr)

    def get_clients(self, client_type):
        ws_list = []
        for client in self.clients:
            ws = client['websocket']
            if ws.type == client_type:
                ws_list.append(client['websocket'])
        return ws_list

    def add_history(self, message):
        self.history.append(message)
        if len(self.history) > self.history_size:
            self.history.pop(0)

    def del_history(self, msg_id):
        if len(msg_id) > 1:
            return

        for index, item in enumerate(self.history):
            if str(item.id) == msg_id[0]:
                self.history.pop(index)

    def get_history(self):
        return self.history

    def process_command(self, command, values):
        if command == 'remove_by_id':
            self._remove_by_id(values.messages)
        elif command == 'remove_by_user':
            self._remove_by_user(values.user)
        elif command == 'replace_by_id':
            self._replace_by_id(values.messages)
        elif command == 'replace_by_user':
            self._replace_by_user(values.user)

    def _remove_by_id(self, ids):
        for item in ids:
            for message in self.history:
                if message.get('id') == item:
                    self.history.remove(message)

    def _remove_by_user(self, users):
        for item in users:
            for message in reversed(self.history):
                if message.user == item:
                    self.history.remove(message)

    def _replace_by_id(self, ids):
        for item in ids:
            for index, message in enumerate(self.history):
                if message.id == item:
                    self.history[index]['text'] = REMOVED_TRIGGER
                    if 'emotes' in self.history[index]:
                        del self.history[index]['emotes']
                    if 'bttv_emotes' in self.history[index]:
                        del self.history[index]['bttv_emotes']

    def _replace_by_user(self, users):
        for item in users:
            for index, message in enumerate(self.history):
                if message.user == item:
                    self.history[index]['text'] = REMOVED_TRIGGER
                    if 'emotes' in self.history[index]:
                        del self.history[index]['emotes']
                    if 'bttv_emotes' in self.history[index]:
                        del self.history[index]['bttv_emotes']


class CssRoot(object):
    def __init__(self):
        self.css_map = {
            'css': self.style_css,
        }
        self.locations = SRC_PATH + "\\themes\\default\\assets\\"

    @cherrypy.expose
    def default(self, *args):
        cherrypy.response.headers['Content-Type'] = 'text/css'
        path = ['css']
        path.extend(args)
        file_type = args[-1].split('.')[-1]
        if file_type in self.css_map:
            return self.css_map[file_type](*path)
        return

    def style_css(self, *path):
        cherrypy.response.headers['Content-Type'] = 'text/css'
        with open(os.path.join(self.locations, *path), 'r') as css:
            return css.read()


class HttpRoot(object):
    def __init__(self):
        self.locations = SRC_PATH + "\\themes\\default\\assets\\"

    @cherrypy.expose
    def index(self):
        cherrypy.response.headers["Expires"] = -1
        cherrypy.response.headers["Pragma"] = "no-cache"
        cherrypy.response.headers["Cache-Control"] = "private, max-age=0, no-cache, no-store, must-revalidate"
        if os.path.exists(self.locations):
            return serve_file(os.path.join(self.locations, 'index.html'), 'text/html')
        else:
            return "Style not found"

    @cherrypy.expose
    def ws(self):
        pass


class SocketThread(threading.Thread):
    def __init__(self, host, port, **kwargs):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.host = host
        self.port = port

        self.root_config = None
        self.css_config = None

        cherrypy.config.update({'server.socket_port': int(self.port),
                                'server.socket_host': self.host,
                                'engine.autoreload.on': False})
        self.websocket = WebChatPlugin(cherrypy.engine)
        self.websocket.subscribe()
        cherrypy.tools.websocket = WebSocketTool()

    def update_settings(self):
        self.root_config = {
            '/ws': {'tools.websocket.on': True,
                    'tools.websocket.handler_cls': WebChatSocketServer},
            '/js': {'tools.staticdir.on': True,
                    'tools.staticdir.dir': os.path.join(SRC_PATH + "\\themes\\default\\assets\\", 'js')},
        }
        self.css_config = {
            '/': {}
        }

    def run(self):
        cherrypy.log.access_file = ''
        cherrypy.log.error_file = ''
        cherrypy.log.screen = True

        # Removing Access logs
        cherrypy.log.access_log.propagate = False
        cherrypy.log.error_log.setLevel(logging.ERROR)

        self.update_settings()
        self.mount_dirs()
        try:
            cherrypy.engine.start()
        except Exception as exc:
            log.error('Unable to start webchat: %s', exc)

    def mount_dirs(self):
        cherrypy.tree.mount(CssRoot(), '/css', self.css_config)
        cherrypy.tree.mount(HttpRoot(), '', self.root_config)


def socket_open(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    return sock.connect_ex((host, int(port)))


class Webchat(MessagingModule):
    def __init__(self, *args, **kwargs):
        MessagingModule.__init__(self, hidden=True, *args, **kwargs)

        self.s_thread = None
        self.queue = kwargs.get('queue')
        self.message_threads = []

    def load_module(self, *args, **kwargs):
        self.start_webserver()

    def start_webserver(self):
        host = "127.0.0.1"
        port = "8000"
        if socket_open(host, port):
            try:
                self.s_thread = SocketThread(host, port)
                self.s_thread.start()
            except:
                log.error('Unable to bind at {}:{}'.format(host, port))

            for thread in range(1):
                self.message_threads.append(MessagingThread())
                self.message_threads[thread].start()
        else:
            log.error("Port is already used, please change webchat port")

    def process_message(self, message, **kwargs):
        if not hasattr(message, 'hidden'):
            s_queue.put(message)
        return message
