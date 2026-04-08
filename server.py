import socket
import threading
import time
import struct
from game import GameState

class GameServer:
    def __init__(self, host='0.0.0.0', port_tcp=35000, port_udp=35001):
        self.host = host
        self.port_tcp = port_tcp
        self.port_udp = port_udp
        self.game_state = GameState()
        self.clients_tcp = []
        self.clients_udp = []
        self.lock = threading.Lock()
        self.running = True
        self.last_update = time.time()
        self.update_rate = 1/60
        
        self.tcp_socket = None
        self.udp_socket = None
        
        self.metrics = {
            'tcp_latencies': [],
            'udp_latencies': [],
            'ball_position_jumps': [],
            'last_ball_pos': (self.game_state.ball.x, self.game_state.ball.y)
        }

    def start(self):
        tcp_thread = threading.Thread(target=self.tcp_listen, daemon=True)
        udp_thread = threading.Thread(target=self.udp_listen, daemon=True)
        update_thread = threading.Thread(target=self.game_loop, daemon=True)
        
        tcp_thread.start()
        udp_thread.start()
        update_thread.start()

    def tcp_listen(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((self.host, self.port_tcp))
        self.tcp_socket.listen(2)
        print(f"Servidor TCP escutando em {self.host}:{self.port_tcp}")
        
        while self.running:
            try:
                client_socket, addr = self.tcp_socket.accept()
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                player_id = len(self.clients_tcp)
                self.clients_tcp.append({
                    'socket': client_socket,
                    'addr': addr,
                    'player_id': player_id,
                    'protocol': 'TCP',
                    'last_ping': time.time()
                })
                threading.Thread(target=self.handle_tcp_client, args=(client_socket, player_id), daemon=True).start()
            except:
                break

    def handle_tcp_client(self, client_socket, player_id):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                with self.lock:
                    receive_time = time.time()
                    send_time = struct.unpack('!d', data[:8])[0]
                    latency = (receive_time - send_time) * 1000
                    self.metrics['tcp_latencies'].append(latency)
                    if len(self.metrics['tcp_latencies']) > 100:
                        self.metrics['tcp_latencies'].pop(0)
                    
                    command = data[8:9].decode()
                    
                    if player_id == 0:
                        if command == 'U':
                            self.game_state.paddle1.move_up()
                        elif command == 'D':
                            self.game_state.paddle1.move_down()
                        elif command == 'S':
                            self.game_state.paddle1.stop()
                    else:
                        if command == 'U':
                            self.game_state.paddle2.move_up()
                        elif command == 'D':
                            self.game_state.paddle2.move_down()
                        elif command == 'S':
                            self.game_state.paddle2.stop()
        except:
            pass
        finally:
            with self.lock:
                self.clients_tcp = [c for c in self.clients_tcp if c['player_id'] != player_id]
            client_socket.close()

    def udp_listen(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind((self.host, self.port_udp))
        print(f"Servidor UDP escutando em {self.host}:{self.port_udp}")
        
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                with self.lock:
                    receive_time = time.time()
                    send_time = struct.unpack('!d', data[:8])[0]
                    latency = (receive_time - send_time) * 1000
                    self.metrics['udp_latencies'].append(latency)
                    if len(self.metrics['udp_latencies']) > 100:
                        self.metrics['udp_latencies'].pop(0)
                    
                    player_id = struct.unpack('!B', data[8:9])[0]
                    command = data[9:10].decode()
                    
                    if player_id == 0:
                        if command == 'U':
                            self.game_state.paddle1.move_up()
                        elif command == 'D':
                            self.game_state.paddle1.move_down()
                        elif command == 'S':
                            self.game_state.paddle1.stop()
                    else:
                        if command == 'U':
                            self.game_state.paddle2.move_up()
                        elif command == 'D':
                            self.game_state.paddle2.move_down()
                        elif command == 'S':
                            self.game_state.paddle2.stop()
                    
                    existing = [c for c in self.clients_udp if c['addr'] == addr]
                    if not existing:
                        self.clients_udp.append({
                            'addr': addr,
                            'player_id': player_id,
                            'protocol': 'UDP'
                        })
            except:
                pass

    def game_loop(self):
        while self.running:
            current_time = time.time()
            if current_time - self.last_update >= self.update_rate:
                with self.lock:
                    old_pos = (self.game_state.ball.x, self.game_state.ball.y)
                    self.game_state.update()
                    new_pos = (self.game_state.ball.x, self.game_state.ball.y)
                    
                    jump = ((new_pos[0] - self.metrics['last_ball_pos'][0])**2 + 
                            (new_pos[1] - self.metrics['last_ball_pos'][1])**2)**0.5
                    
                    if jump > 20:
                        self.metrics['ball_position_jumps'].append(jump)
                        if len(self.metrics['ball_position_jumps']) > 100:
                            self.metrics['ball_position_jumps'].pop(0)
                    
                    self.metrics['last_ball_pos'] = new_pos
                    
                    state_data = self.game_state.serialize()
                    
                    for client in self.clients_tcp:
                        try:
                            client['socket'].send(state_data)
                        except:
                            pass
                    
                    for client in self.clients_udp:
                        try:
                            self.udp_socket.sendto(state_data, client['addr'])
                        except:
                            pass
                
                self.last_update = current_time
            
            time.sleep(0.001)

    def stop(self):
        self.running = False
        if self.tcp_socket:
            self.tcp_socket.close()
        if self.udp_socket:
            self.udp_socket.close()

    def get_metrics(self):
        with self.lock:
            tcp_avg = sum(self.metrics['tcp_latencies']) / len(self.metrics['tcp_latencies']) if self.metrics['tcp_latencies'] else 0
            udp_avg = sum(self.metrics['udp_latencies']) / len(self.metrics['udp_latencies']) if self.metrics['udp_latencies'] else 0
            jump_avg = sum(self.metrics['ball_position_jumps']) / len(self.metrics['ball_position_jumps']) if self.metrics['ball_position_jumps'] else 0
            
            return {
                'tcp_latency_ms': tcp_avg,
                'udp_latency_ms': udp_avg,
                'avg_ball_jump': jump_avg,
                'tcp_latency_min_max': (min(self.metrics['tcp_latencies']) if self.metrics['tcp_latencies'] else 0, max(self.metrics['tcp_latencies']) if self.metrics['tcp_latencies'] else 0),
                'udp_latency_min_max': (min(self.metrics['udp_latencies']) if self.metrics['udp_latencies'] else 0, max(self.metrics['udp_latencies']) if self.metrics['udp_latencies'] else 0)
            }


if __name__ == '__main__':
    server = GameServer('127.0.0.1', 35000, 35001)
    print("Iniciando servidor Ping Pong...")
    server.start()
    print("Servidor iniciado!")
    
    try:
        while True:
            time.sleep(5)
            metrics = server.get_metrics()
            print(f"TCP Latency: {metrics['tcp_latency_ms']:.2f}ms | UDP Latency: {metrics['udp_latency_ms']:.2f}ms | Avg Ball Jump: {metrics['avg_ball_jump']:.2f}px")
    except KeyboardInterrupt:
        server.stop()
