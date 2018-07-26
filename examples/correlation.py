# -*- coding: utf-8 -*-
import sys

import binascii
import time
from gor.middleware import TornadoGor


PY3 = sys.version_info >= (3,)
TOKEN_NAME = 'JSESSIONID'

"""
Stores prometheus counters and provides an interface to push metrics with custom labels
"""
class Tokens:
    def __init__(self):
        self.tokens = {}

    def get_token_value(self, name, original_value):
        """
        Retrieves the latest observed value for the specified token, original_value pair.
        :param name: The name of the token to look for.
        :param original_value: The value of the token in the original response gathered during the recording
        :return value: the value of the token in the last replayed sample or an epmty string
        :return found: True if the new value of the token has been found, False otherwise
        """
        if name in self.tokens:
            if original_value in self.tokens[name]:
                return self.tokens[name][original_value], True
            elif None in self.tokens[name]:
                return self.tokens[name][None], True
        return "", False

    def observe_token_value(self, name, observed_value, original_value=None):
        """
        Observe a new value for the specified token, optionally the original token value observed when recording
        can be specified for correlation
        :param name: The name of the observed token
        :param observed_value: The value of the observed token
        :param original_value: (Optional) the original_value of the token
        """
        if observed_value is None and original_value is None:
            return
        if name not in self.tokens:
            self.tokens[name] = {}
        self.tokens[name][original_value] = observed_value



def log(msg):
    """
    Logging to STDERR as STDOUT and STDIN used for data transfer
    @type msg: str or byte string
    @param msg: Message to log to STDERR
    """
    try:
        msg = str(msg) + '\n'
    except:
        pass
    sys.stderr.write(msg)
    sys.stderr.flush()

def gor_hex_data(data):
    if PY3:
        data = b''.join(
            map(lambda x: binascii.hexlify(x)
                if isinstance(x, bytes) else binascii.hexlify(x.encode()),
                [data.raw_meta, '\n', data.http])) + b'\n'
        return data.decode('utf-8')
    else:
        return ''.join(map(lambda x: binascii.hexlify(x),
                           [data.raw_meta, '\n', data.http])) + '\n'


def on_request(proxy, msg, **kwargs):
    tokens = kwargs['tokens']
    # TODO: modify timestamp and move requests that can not be correlated back in the queue
    proxy.on('response', on_response, idx=msg.id, req=msg, tokens=tokens)
    log("Processing Request: {}".format(msg.id))

    # Modify the token
    request_cookie = proxy.http_cookie(msg.http, TOKEN_NAME)
    if request_cookie is not None:
        updated_token, token_found = tokens.get_token_value(TOKEN_NAME, request_cookie)
        new_msg = msg
        if not token_found:
            log("Request contains Cookie {}={} - not updating it".format(TOKEN_NAME,request_cookie))
        else:
            log("Modifying {} Cookie from {} to {}".format(TOKEN_NAME, request_cookie, updated_token))
            new_msg.http = proxy.set_http_cookie(msg.http, TOKEN_NAME, updated_token)
        return new_msg


def on_response(proxy, msg, **kwargs):
    tokens = kwargs['tokens']
    proxy.on('replay', on_replay, idx=kwargs['req'].id, req=kwargs['req'], resp=msg, tokens=tokens)


def on_replay(proxy, msg, **kwargs):
    tokens = kwargs['tokens']

    # Look for tokens to be saved in the Set-Cookie of the response
    request_cookie = proxy.http_cookie(kwargs['req'].http, TOKEN_NAME)
    original_response_cookie = proxy.http_cookie(kwargs['resp'].http, TOKEN_NAME, header_name='Set-Cookie')
    replayed_response_cookie = proxy.http_cookie(msg.http, TOKEN_NAME, header_name='Set-Cookie')
    time.sleep(5)
    tokens.observe_token_value(TOKEN_NAME, replayed_response_cookie, original_response_cookie)

    # Debug
    log("Replayed Response")
    log("Request ID: {}".format(msg.id))
    log("Request Cookie: {} ".format(request_cookie))
    log("Original Response Set-Cookie: {} ".format(original_response_cookie))
    log("Replayed Response Set-Cookie: {} ".format(replayed_response_cookie))

    # Check Status consistency between original response and replay
    replay_status = proxy.http_status(msg.http)
    resp_status = proxy.http_status(kwargs['resp'].http)
    if replay_status != resp_status:
        log('replay status [%s] diffs from response status [%s]\n' % (replay_status, resp_status))
    else:
        log('replay status is same as response status\n')
    # log('Received Response {}'.format(msg.http))

if __name__ == '__main__':
    toks = Tokens()
    proxy = TornadoGor()
    proxy.setup_prometheus(enable=True, port=8000)
    # Set the first handler (others are initialized as needed within this one)
    proxy.on('request', on_request, tokens=toks)

    log('Starting Proxy')
    proxy.run()


