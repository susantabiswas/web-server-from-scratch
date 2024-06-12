import socket
import selectors
import types
import sys

HOST = "localhost" # loopback 127.0.0.1
PORT = 56123

# max bytes to read at a time
READ_BUFF = 1024

# register for monitoring the socket
io_selector = selectors.DefaultSelector()


def single_connection_server():
    # TCP + ipv4 server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))

        # Start listening for incoming connection requests on this endpoint
        # It maintains a queue of incoming requests, the `backlog` param defines the
        # queue length. Only when .accept() is called, a req is dequeued
        s.listen() 

        print(f'[Single connection server] Started listening on {HOST}:{PORT}')
        
        # 3 way TCP handshake
        # Note - Blocking call, blocks execution till a conn is received
        conn, addr = s.accept()
        
        with conn:
            print(f"Client address: {addr}")

            # read data stream till we are getting data from client
            while True:
                # Note - it is possible that recv can receive data < READ_BUFF
                data = conn.recv(READ_BUFF)

                # empty byte data recieved
                if not data:
                    break

                # just echo the data
                # Note - same as recv, .send() doesnt guarantee that all the data is sent
                # in one go, sendall() abstraction will send everything (keeps sending till end reached)
                conn.sendall(data)

    print("Stopped listening....")


# Concurrent connection request using I/O multiplexing
# TCP + IPV4 server
def concurrent_connection_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        print(f'[Concurrent connection server] Started listening on {HOST}:{PORT}')

        # Now the calls made using this socket wont be blocking
        s.setblocking(False)

        # this endpoint will now be monitored for socket events
        io_selector.register(s, selectors.EVENT_READ, data=None)

        try:
            # this event loop will be used to check for any monitored events
            while True:
                # Note - Blocking call till there are sockets ready for IO
                events = io_selector.select(timeout=None)
                
                # key: .fileobj contains the socket obj, .data = socket conn data
                # mask: mask that indicates the socket events ready on the
                # socket connection
                for key, mask in events:
                    # new incoming connection request on the socket 
                    # (for a new conn, data wont be set)
                    if key.data is None:
                        connection_request_accept_handler(key.fileobj)
                    else:
                        serve_connection_request(key, mask)
        except KeyboardInterrupt:
            print('Received signal to stop the server....')
        finally:
            print(f'Server listening on {HOST}: {PORT} closed....')


def connection_request_accept_handler(sock):
    connection, addr = sock.accept()

    print(f'Accepted connection from {addr}')

    # make this conn non-blocking
    connection.setblocking(False)

    # we will pass data obj (SimpleNamespace allows to init obj with attributes)
    # to track the in/out data for this connection
    data = types.SimpleNamespace(addr=addr, received=b'', send=b'')
    # events to monitor: selector will notify when socket has data for read/write
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    io_selector.register(connection, events=events, data=data)



def serve_connection_request(key, mask):
    sock = key.fileobj
    data = key.data

    # this connection might have a read,write events
    # we handle them accordingly. We will check for all the events
    # we specified in the 'mask' while registering this conn with selector

    # !!! NOTE - We will only send or recieve data as per the buffer length
    # this ensures that one conn doesnt affect the other connections
    # eg: one connection might have much more data compared to other conns

    # conn received data from client
    if mask & selectors.EVENT_READ:
        data_recv = sock.recv(READ_BUFF)

        if not data_recv:
            print(f'End of data, closing connection with {data.addr}')
            io_selector.unregister(sock)
            sock.close()
            
        # to echo the data received from client, we add it to the
        # data to send for this conn
        data.send += data_recv

    # server has data ready to send to the client
    if mask & selectors.EVENT_WRITE:
        if data.send:
            sent_len = sock.send(data.send)
            print(f'Sent data to {data.addr} -> Len: {sent_len}, Data: {data.send}')
            # remove the data sent from the data_to_send 
            data.send = data.send[sent_len:]


# single_connection_server()

concurrent_connection_server()