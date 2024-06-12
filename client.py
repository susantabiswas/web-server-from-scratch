import socket
import types
import selectors

HOST = "127.0.0.1"
PORT = 56123

NUM_CONNECTIONS = 3

READ_BUFF = 1024

io_selector = selectors.DefaultSelector()

all_data = [b'Test message 1', b'Second test message']


def single_client_connection():
    # IPV4 + TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(b"Hello")
        data = s.recv(1024)

    print(f'Recieved data from server: {data}')


def create_connection(conn_id, data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # start a non-blocking connection
    sock.setblocking(False)
    sock.connect_ex((HOST, PORT)) # Doesnt raise blocking IO exception unlike .connect()

    print(f'Connection {conn_id} established with {HOST}: {PORT}')

    # monitor read and write events for this connection
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    data = types.SimpleNamespace(
            conn_id=conn_id,
            addr=(HOST, PORT),
            data_len=sum(len(d) for d in data),
            data=data.copy(),
            data_recv=0,
            send=b''
        )

    # register this connection for IO multiplexing monitoring
    io_selector.register(sock, events, data=data)
        

def connection_request_handler(key, mask):
    sock = key.fileobj
    conn_data = key.data

    # data received
    if mask & selectors.EVENT_READ:
        data_recv = sock.recv(READ_BUFF)

        if len(data_recv):
            conn_data.data_recv += len(data_recv)
            print(f'[Conn: {conn_data.conn_id}] Received {len(data_recv)} bytes of data \
                    from {conn_data.addr}, recieved: {data_recv}, \
                    progress: {conn_data.data_recv}/{conn_data.data_len}')

        if not data_recv or conn_data.data_recv == conn_data.data_len:
            print(f'[Conn: {conn_data.conn_id}] Closing connection, end of response from {conn_data.addr} ....')
            io_selector.unregister(sock)
            sock.close()
            
        
    # data left to send
    if mask & selectors.EVENT_WRITE:
        # if data_to_send is empty, check if there are any messages
        # left to send
        if len(conn_data.send) == 0 and len(conn_data.data):
            conn_data.send += conn_data.data.pop(0)

        if len(conn_data.send):
            sent_len = sock.send(conn_data.send)
            print(f'[Conn: {conn_data.conn_id}] Sent {sent_len} bytes of data \
                to {conn_data.addr}, sent: {conn_data.send[:sent_len]}')

            conn_data.send = conn_data.send[sent_len:]
            

def multi_connection_client(num_conn=NUM_CONNECTIONS, data=all_data):\
    # create connections with the server
    for conn_id in range(1, num_conn+1):
        create_connection(conn_id=conn_id, data=data)

    try:
        # We use IO multiplexing for catering the connections on the sockets
        while True:
            # if there are no sockets to monitor, exit
            # .get_map() returns the mappings of sockets tracked
            if not io_selector.get_map():
                break

            events = io_selector.select(timeout=None)

            for key, mask in events:
                connection_request_handler(key, mask)
            
    except KeyboardInterrupt:
        print(f'Received signal to exit, exiting....')
    finally:
        io_selector.close()


# single_client_connection()
multi_connection_client(3, data=all_data)