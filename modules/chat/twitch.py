# -*- coding: utf-8 -*-
import random
import re
import threading
import queue as Queue
import logging
import time
import requests

import irc.client
import irc
from modules.helper.message import *
from modules.helper.parser import update
from modules.helper.system import EMOTE_FORMAT

log = logging.getLogger('twitch')
log.level = logging.DEBUG
headers = {'Client-ID': '1geb38b014aaz3edkuth43txob2q4h'}
headers_v5 = {'Client-ID': '1geb38b014aaz3edkuth43txob2q4h',
              'Accept': 'application/vnd.twitchtv.v5+json'}
PING_DELAY = 10
SYSTEM_USER = 'Twitch.TV'
NOT_FOUND = 'none'
EMOTE_SMILE_URL = 'http://static-cdn.jtvnw.net/emoticons/v1/{id}/1.0'
BTTV_EMOTE_SMILE_URL = 'https://cdn.betterttv.net/emote/{0}/2x'


class TwitchUserError(Exception):
    """Exception for twitch user error"""


class TwitchTextMessage(TextMessage):
    def __init__(self, user, text, me):
        self.bttv_emotes = {}
        self.bits = {}
        TextMessage.__init__(self, platform_id=SOURCE, icon=SOURCE_ICON,
                             user=user, text=text, me=me)


class TwitchSystemMessage(SystemMessage):
    def __init__(self, text, category='system', **kwargs):
        SystemMessage.__init__(self, text, platform_id=SOURCE, icon=SOURCE_ICON,
                               user=SYSTEM_USER, category=category, **kwargs)


class TwitchEmote(Emote):
    def __init__(self, emote_id, emote_url, positions):
        Emote.__init__(self, emote_id=emote_id, emote_url=emote_url)
        self.positions = positions


class TwitchMessageHandler(threading.Thread):
    def __init__(self, queue, twitch_queue, **kwargs):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.message_queue = queue
        self.twitch_queue = twitch_queue
        self.source = SOURCE

        self.irc_class = kwargs.get('irc_class')  # type: IRC
        self.nick = kwargs.get('nick')
        self.bttv = kwargs.get('bttv_smiles_dict', {})
        self.badges = kwargs.get('badges')
        self.custom_badges = kwargs.get('custom_badges')
        self.bits = self._reformat_bits(kwargs.get('bits'))

    def run(self):
        while True:
            self.process_message(self.twitch_queue.get())

    def process_message(self, msg):
        # After we receive the message we have to process the tags
        # There are multiple things that are available, but
        #  for now we use only display-name, which is case-able.
        # Also, there is slight problem with some users, they don't have
        #  the display-name tag, so we have to check their "real" username
        #  and capitalize it because twitch does so, so we do the same.
        if msg.type in ['pubmsg']:
            self._handle_message(msg)
        elif msg.type in ['action']:
            self._handle_message(msg, me=True)
        elif msg.type in ['clearchat']:
            self._handle_clearchat(msg)
        elif msg.type in ['usernotice']:
            self._handle_usernotice(msg)

    def _handle_badges(self, message, badges):
        for badge in badges.split(','):
            badge_tag, badge_size = badge.split('/')
            # Fix some of the names
            badge_tag = badge_tag.replace('moderator', 'mod')
            if badge_tag in self.custom_badges:
                badge_info = self.custom_badges.get(badge_tag)['versions'][badge_size]
                url = badge_info.get('image_url_4x',
                                     badge_info.get('image_url_2x',
                                                    badge_info.get('image_url_1x')))
            elif badge_tag in self.badges:
                badge_info = self.badges.get(badge_tag)
                if 'svg' in badge_info:
                    url = badge_info.get('svg')
                elif 'image' in badge_info:
                    url = badge_info.get('image')
                else:
                    url = 'none'
            else:
                url = NOT_FOUND
            message.badges.append(Badge(badge_tag, url))

    def _handle_usernotice(self, msg):
        for tag in msg.tags:
            tag_key, tag_value = tag.values()
            if tag_key == 'system-msg':
                msg_text = tag_value
                self.irc_class.system_message(msg_text, category='chat')
                break
        if msg.arguments:
            self._handle_message(msg, sub_message=True)

    def _handle_clearchat(self, msg, text=None):
        pass

    def _handle_bits(self, message, total_amount):
        pass

    def _handle_viewer_color(self, message, value):
        message.nick_colour = value

    @staticmethod
    def _handle_display_name(message, name):
        message.user = name if name else message.user

    @staticmethod
    def _handle_emotes(message, tag_value):
        for emote in tag_value.split('/'):
            emote_id, emote_pos_diap = emote.split(':')
            message.emotes.append(
                TwitchEmote(emote_id,
                            EMOTE_SMILE_URL.format(id=emote_id),
                            emote_pos_diap.split(','))
            )

    def _handle_bttv_smiles(self, message):
        for word in message.text.split():
            if word in self.bttv:
                bttv_smile = self.bttv.get(word)
                message.bttv_emotes[bttv_smile['code']] = Emote(
                    bttv_smile['code'],
                    BTTV_EMOTE_SMILE_URL.format(bttv_smile['id'])
                )

    @staticmethod
    def _handle_sub_message(message):
        message.sub_message = True
        message.jsonable += ['sub_message']

    def _handle_pm(self, message):
        if re.match('^@?{0}[ ,]?'.format(self.nick), message.text.lower()):
                message.pm = True

    def _handle_message(self, msg, sub_message=False, me=False):
        message = TwitchTextMessage(msg.source.split('!')[0], msg.arguments.pop(), me)
        if message.user == 'twitchnotify':
            self.irc_class.queue.put(TwitchSystemMessage(message.text, category='chat'))
            print(message)
        for tag in msg.tags:
            tag_key, tag_value = tag.values()
            if tag_key == 'display-name':
                self._handle_display_name(message, tag_value)
            elif tag_key == 'badges' and tag_value:
                self._handle_badges(message, tag_value)
            elif tag_key == 'emotes' and tag_value:
                self._handle_emotes(message, tag_value)
            elif tag_key == 'bits' and tag_value:
                self._handle_bits(message, int(tag_value))
            elif tag_key == 'color' and tag_value:
                self._handle_viewer_color(message, tag_value)
        self._handle_bttv_smiles(message)
        self._handle_pm(message)

        if sub_message:
            self._handle_sub_message(message)

        self._send_message(message)

    def _send_message(self, message):
        self._post_process_emotes(message)
        self._post_process_bttv_emotes(message)
        self._post_process_multiple_channels(message)
        self.message_queue.put(message)

    @staticmethod
    def _post_process_emotes(message):
        conveyor_emotes = []
        for emote in message.emotes:
            for position in emote.positions:
                start, end = position.split('-')
                conveyor_emotes.append({'emote_id': emote.id,
                                        'start': int(start),
                                        'end': int(end)})
        conveyor_emotes = sorted(conveyor_emotes, key=lambda k: k['start'], reverse=True)

        for emote in conveyor_emotes:
            message.text = u'{start}{emote}{end}'.format(start=message.text[:emote['start']],
                                                         end=message.text[emote['end'] + 1:],
                                                         emote=EMOTE_FORMAT.format(emote['emote_id']))

    def _post_process_multiple_channels(self, message):
        channel_class = self.irc_class.main_class
        message.channel_name = channel_class.display_name

    @staticmethod
    def _post_process_bttv_emotes(message):
        for emote, data in message.bttv_emotes.items():
            message.text = message.text.replace(emote, EMOTE_FORMAT.format(emote))
            message.emotes.append(data)

    @staticmethod
    def _reformat_bits(bits):
        pass


class IRC(irc.client.SimpleIRCClient):
    def __init__(self, queue, channel, **kwargs):
        irc.client.SimpleIRCClient.__init__(self)
        self.channel = "#" + channel.lower()
        self.queue = queue
        self.nick = channel.lower()
        self.twitch_queue = Queue.Queue()
        self.tw_connection = None
        self.main_class = kwargs.get('main_class')
        self.msg_handler = TwitchMessageHandler(queue, self.twitch_queue,
                                                irc_class=self,
                                                nick=self.nick,
                                                **kwargs)
        self.msg_handler.start()

    def system_message(self, message, category='system'):
        self.queue.put(TwitchSystemMessage(message, category=category, channel_name=self.nick))

    def on_welcome(self, connection, event):
        log.info("Welcome Received, joining {0} channel".format(self.channel))
        log.debug("event: {}".format(event))
        self.tw_connection = connection

        connection.join(self.channel)
        connection.cap('REQ', ':twitch.tv/tags')
        connection.cap('REQ', ':twitch.tv/commands')

        ping_handler = TwitchPingHandler(connection, self.main_class, self)
        ping_handler.start()

    def on_pubmsg(self, connection, event):
        log.debug("connection: {}".format(connection))
        log.debug("event: {}".format(event))
        # print(event)
        self.twitch_queue.put(event)

    def on_action(self, connection, event):
        log.debug("connection: {}".format(connection))
        log.debug("event: {}".format(event))
        # print(event)
        self.twitch_queue.put(event)

    def on_clearchat(self, connection, event):
        log.debug("connection: {}".format(connection))
        log.debug("event: {}".format(event))
        # print(event)
        self.twitch_queue.put(event)

    def on_usernotice(self, connection, event):
        log.debug("connection: {}".format(connection))
        log.debug("event: {}".format(event))
        # print(event)
        self.twitch_queue.put(event)

    def on_disconnect(self, connection, event):
        self.twitch_queue.put(event)

    def on_join(self, connection, event):
        self.twitch_queue.put(event)


class TwitchPingHandler(threading.Thread):
    def __init__(self, irc_connection, main_class, irc_class):
        threading.Thread.__init__(self)
        self.irc_connection = irc_connection
        self.main_class = main_class
        self.irc_class = irc_class

    def run(self):
        log.info("Ping started")
        while self.irc_connection.connected:
            self.irc_connection.ping("keep-alive")
            time.sleep(PING_DELAY)


class TWChannel(threading.Thread):
    def __init__(self, queue, host, port, channel, bttv_smiles, anon=True, **kwargs):
        threading.Thread.__init__(self)
        self.bttv_smiles = bttv_smiles
        self.daemon = True
        self.queue = queue

        self.host = host
        self.port = port
        self.channel = channel
        self.display_name = None
        self.channel_id = None
        self.irc = None
        self.kwargs = kwargs

        if bttv_smiles:
            self.kwargs['bttv_smiles_dict'] = {}

        if anon:
            nick_length = 14
            self.nickname = "justinfan"

            for number in range(0, nick_length):
                self.nickname += str(random.randint(0, 9))

    def run(self):
        try_count = 0
        # We are connecting via IRC handler.
        while True:
            try_count += 1
            log.info("Connecting, try {0}".format(try_count))
            try:
                if self.load_config():
                    self.irc = IRC(self.queue, self.channel, main_class=self, **self.kwargs)
                    self.irc.connect(self.host, self.port, self.nickname)
                    self.irc.start()
                    log.info("Connection closed")
                    break
            except Exception as exc:
                log.exception(exc)
            time.sleep(5)

    def load_config(self):
        try:
            request = requests.get("https://api.twitch.tv/kraken/channels/{0}".format(self.channel), headers=headers)
            if request.status_code == 200:
                log.info("Channel found? continuing")
                data = request.json()
                self.display_name = data['display_name']
                self.channel_id = data['_id']
            elif request.status_code == 404:
                raise TwitchUserError
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except TwitchUserError:
            raise TwitchUserError
        except Exception as exc:
            log.error("Unable to get channel ID, error: {0}\nArgs: {1}".format(exc, exc.args))
            return False
        try:
            # Getting random IRC server to connect to
            request = requests.get("http://tmi.twitch.tv/servers?channel={0}".format(self.channel))
            if request.status_code == 200:
                self.host = random.choice(request.json()['servers']).split(':')[0]
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.error("Unable to get server list, error: {0}\nArgs: {1}".format(exc, exc.args))
            return False

        try:
            # Getting Better Twitch TV smiles
            if self.bttv_smiles:
                request = requests.get("https://api.betterttv.net/2/emotes", timeout=10)
                if request.status_code == 200:
                    for smile in request.json()['emotes']:
                        self.kwargs['bttv_smiles_dict'][smile.get('code')] = smile
                    log.info("Got global bttv emotes for channel: {0}".format(self.channel))
                else:
                    raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get BTTV smiles, error {0}\nArgs: {1}".format(exc, exc.args))


        try:
            # Getting Better Twitch TV channel smiles
            if self.bttv_smiles:
                request = requests.get("https://api.betterttv.net/2/channels/{0}".format(self.channel), timeout=10)
                if request.status_code == 200:
                    for smile in request.json()['emotes']:
                        self.kwargs['bttv_smiles_dict'][smile.get('code')] = smile
                    log.info("Got channel depended bttv emotes for: {0}".format(self.channel))
                else:
                    raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get BTTV smiles, error {0}\nArgs: {1}".format(exc, exc.args))

        try:
            # Getting standard twitch badges
            request = requests.get("https://api.twitch.tv/kraken/chat/{0}/badges".format(self.channel), headers=headers)
            if request.status_code == 200:
                self.kwargs['badges'] = request.json()
                log.info("Got global badges for: {0}".format(self.channel))
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get twitch badges, error {0}\nArgs: {1}".format(exc, exc.args))

        try:
            # Getting CUSTOM twitch badges
            request = requests.get("https://badges.twitch.tv/v1/badges/global/display")
            if request.status_code == 200:
                self.kwargs['custom_badges'] = request.json()['badge_sets']
                log.info("Got custom badges for: {0}".format(self.channel))
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get twitch undocumented api badges, error {0}\n"
                        "Args: {1}".format(exc, exc.args))
        try:
            # Getting CUSTOM twitch badges
            badges_url = "https://badges.twitch.tv/v1/badges/channels/{0}/display"
            request = requests.get(badges_url.format(self.channel_id))
            if request.status_code == 200:
                update(self.kwargs['custom_badges'], request.json()['badge_sets'])
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get twitch undocumented api badges, error {0}\n"
                        "Args: {1}".format(exc, exc.args))

        try:
            bits_url = "https://api.twitch.tv/kraken/bits/actions/?channel_id={}"
            request = requests.get(bits_url.format(self.channel_id), headers=headers_v5)
            if request.status_code == 200:
                data = request.json()['actions']
                self.kwargs['bits'] = {item['prefix'].lower(): item for item in data}
            else:
                raise Exception("Not successful status code: {0}".format(request.status_code))
        except Exception as exc:
            log.warning("Unable to get twitch undocumented api badges, error {0}\n"
                        "Args: {1}".format(exc, exc.args))
        return True
