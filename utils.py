import config


def send_message(sock, message):
    sock.sendall("PRIVMSG #{} :{}\r\n".format(config.CHAN, message).encode())
