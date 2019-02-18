import Vue from 'vue'
import DOMPurify from 'dompurify'
import twemoji from 'twemoji'
import VueChatScroll from 'vue-chat-scroll'
Vue.use(VueChatScroll);

(function (WebSocket, Vue, Sanitizer) {
    "use strict";
    new Vue({
        el: "#chat-container",
        data: function () {
            var wsUrl = "ws://" + window.location.host + window.location.pathname+"ws";
            var messages = [];
            var socket = new WebSocket(wsUrl);

            return {
                messages: messages,
                url: wsUrl,
                socket: socket,
                messagesLimit: 30
            };
        },
        created: function () {
            var self = this;

            self.socket.onmessage = this.onmessage;
            self.socket.onopen = this.onopen;
            self.socket.onclose = this.onclose;
        },
        methods: {
            sanitize: function (message) {
                var sanitized = Sanitizer.sanitize(message.text, { ALLOWED_TAGS: [] });
                var clean = this.replaceEmotions(sanitized, message.emotes);
                // if (!clean) this.remove(message);

                return clean;
            },
            replaceEmotions: function (message, emotes) {
                var tw_message = twemoji.parse(message);
                return emotes.reduce(function (m, emote) {
                    var regex = new RegExp(emote.id, 'g');
                    return m.replace(regex, '<img class="smile" src="' + emote.url + '" />')
                    },
                    tw_message);
            },
            onmessage: function (event) {
                var message = JSON.parse(event.data);
                var date = new Date();
                message.payload.time = date.getHours() +":"+ date.getMinutes();
                this.messages.push(message.payload);
            },
            onopen: function () {
                this.attempts = 0;
                if (!this.socketInterval) {
                    clearInterval(this.socketInterval);
                    this.socketInterval = null;
                }
            },
            // onclose: function () {
            //     this.socketInterval = setInterval(this.reconnect, 1000);
            // },
            reconnect: function () {
                this.attempts++;

                this.socket = new WebSocket(this.url);
            },
        }
    });
})(window.WebSocket, Vue, DOMPurify);
