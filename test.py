import os

import cherrypy
from cherrypy.lib.static import serve_file
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import EchoWebSocket
from modules.helper.system import ROOT_PATH, SRC_PATH


def main():
    cherrypy.config.update({'localhost': 8080})
    WebSocketPlugin(cherrypy.engine).subscribe()
    cherrypy.tools.websocket = WebSocketTool()

    class Root(object):
        def __init__(self):
            self.locations = SRC_PATH+"\\themes\\"
        @cherrypy.expose
        def index(self):
            return serve_file(os.path.join(self.locations, 'index.html'), 'text/html')

        @cherrypy.expose
        def ws(self):
            pass

    cherrypy.quickstart(Root(), '/', config={'/ws': {'tools.websocket.on': True,
                                                     'tools.websocket.handler_cls': EchoWebSocket},
                                             '/js': {'tools.staticdir.on': True,
                                                     'tools.staticdir.dir': os.path.join(SRC_PATH+"\\themes", 'js')},
                                             '/css': {'tools.staticdir.on': True,
                                                      'tools.staticdir.dir': os.path.join(SRC_PATH+"\\themes", 'css')}
                                             })



if __name__ == '__main__':
    main()