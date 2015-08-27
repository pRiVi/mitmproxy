from __future__ import (absolute_import, print_function, division)

from netlib.http.http1 import HTTP1Protocol
from netlib.http.http2 import HTTP2Protocol

from .rawtcp import RawTcpLayer
from .tls import TlsLayer
from .http import Http1Layer, Http2Layer


class RootContext(object):
    """
    The outmost context provided to the root layer.
    As a consequence, every layer has .client_conn, .channel, .next_layer() and .config.
    """

    def __init__(self, client_conn, config, channel):
        self.client_conn = client_conn  # Client Connection
        self.channel = channel  # provides .ask() method to communicate with FlowMaster
        self.config = config  # Proxy Configuration

    def next_layer(self, top_layer):
        """
        This function determines the next layer in the protocol stack.

        Arguments:
            top_layer: the current top layer.

        Returns:
            The next layer
        """

        # 1. Check for --ignore.
        if self.config.check_ignore(top_layer.server_conn.address):
            return RawTcpLayer(top_layer)

        # 2. Check for TLS
        # TLS ClientHello magic, works for SSLv3, TLSv1.0, TLSv1.1, TLSv1.2
        # http://www.moserware.com/2009/06/first-few-milliseconds-of-https.html#client-hello
        d = top_layer.client_conn.rfile.peek(3)
        is_tls_client_hello = (
            len(d) == 3 and
            d[0] == '\x16' and
            d[1] == '\x03' and
            d[2] in ('\x00', '\x01', '\x02', '\x03')
        )
        if is_tls_client_hello:
            return TlsLayer(top_layer, True, True)

        # 3. Check for --tcp
        if self.config.check_tcp(top_layer.server_conn.address):
            return RawTcpLayer(top_layer)

        # 4. Check for TLS ALPN (HTTP1/HTTP2)
        if isinstance(top_layer, TlsLayer):
            alpn = top_layer.client_conn.get_alpn_proto_negotiated()
            if alpn == HTTP2Protocol.ALPN_PROTO_H2:
                return Http2Layer(top_layer, 'transparent')
            if alpn == HTTP1Protocol.ALPN_PROTO_HTTP1:
                return Http1Layer(top_layer, 'transparent')

        # 5. Assume HTTP1 by default
        return Http1Layer(top_layer, 'transparent')

        # In a future version, we want to implement TCP passthrough as the last fallback,
        # but we don't have the UI part ready for that.
        #
        # d = top_layer.client_conn.rfile.peek(3)
        # is_ascii = (
        #     len(d) == 3 and
        #     all(x in string.ascii_letters for x in d)  # better be safe here and don't expect uppercase...
        # )
        # # TODO: This could block if there are not enough bytes available?
        # d = top_layer.client_conn.rfile.peek(len(HTTP2Protocol.CLIENT_CONNECTION_PREFACE))
        # is_http2_magic = (d == HTTP2Protocol.CLIENT_CONNECTION_PREFACE)

    @property
    def layers(self):
        return []

    def __repr__(self):
        return "RootContext"
