import socket
import struct
import threading
import time
import turtle
import sys
from game import GameState, Ball, Paddle

class GameClient:
    def __init__(self, server_host='localhost', player_id=0, protocol='TCP'):
        self.server_host = server_host
        self.server_port_tcp = 25000
        self.server_port_udp = 25001
        self.player_id = player_id
        self.protocol = protocol.upper()
        
        self.game_state = GameState()
        self.socket = None
        self.running = True
        self.lock = threading.Lock()
        
        self.last_key_state = {'U': False, 'D': False}
        self.last_sent = time.time()
        self.send_rate = 1/60
        
        self.metrics = {
            'latencies': [],
            'position_interpolations': [],
            'position_extrapolations': []
        }
        
        self.screen = turtle.Screen()
        self.screen.setup(width=800, height=600)
        self.screen.title(f"Ping Pong - {protocol} - Player {player_id}")
        self.screen.bgcolor("black")
        
        self.ball_sprite = turtle.Turtle()
        self.ball_sprite.shape("circle")
        self.ball_sprite.color("white")
        self.ball_sprite.penup()
        
        self.paddle_l = turtle.Turtle()
        self.paddle_l.shape("square")
        self.paddle_l.color("white")
        self.paddle_l.penup()
        self.paddle_l.shapesize(stretch_wid=7, stretch_len=1)
        
        self.paddle_r = turtle.Turtle()
        self.paddle_r.shape("square")
        self.paddle_r.color("white")
        self.paddle_r.penup()
        self.paddle_r.shapesize(stretch_wid=7, stretch_len=1)
        
        self.score_display = turtle.Turtle()
        self.score_display.hideturtle()
        self.score_display.color("white")
        self.score_display.penup()
        self.score_display.goto(0, 250)
        
        self.metrics_display = turtle.Turtle()
        self.metrics_display.hideturtle()
        self.metrics_display.color("yellow")
        self.metrics_display.penup()
        self.metrics_display.goto(-390, 280)
        
        self.screen.onkey(lambda: self.key_press('U'), "Up")
        self.screen.onkey(lambda: self.key_press('D'), "Down")
        self.screen.onkey(lambda: self.key_release('U'), "Up")
        self.screen.onkey(lambda: self.key_release('D'), "Down")
        self.screen.listen()

    def connect(self):
        if self.protocol == 'TCP':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port_tcp))
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def key_press(self, key):
        self.last_key_state[key] = True

    def key_release(self, key):
        self.last_key_state[key] = False

    def send_input(self):
        while self.running:
            current_time = time.time()
            if current_time - self.last_sent >= self.send_rate:
                with self.lock:
                    command = 'S'
                    if self.last_key_state['U']:
                        command = 'U'
                    elif self.last_key_state['D']:
                        command = 'D'
                    
                    send_time = current_time
                    
                    if self.protocol == 'TCP':
                        data = struct.pack('!d', send_time) + command.encode()
                        try:
                            self.socket.send(data)
                        except:
                            pass
                    else:
                        data = struct.pack('!d', send_time) + struct.pack('!B', self.player_id) + command.encode()
                        try:
                            self.socket.sendto(data, (self.server_host, self.server_port_udp))
                        except:
                            pass
                
                self.last_sent = current_time
            
            time.sleep(0.001)

    def receive_state(self):
        while self.running:
            try:
                if self.protocol == 'TCP':
                    data = self.socket.recv(1024)
                else:
                    data, _ = self.socket.recvfrom(1024)
                
                if not data:
                    break
                
                with self.lock:
                    receive_time = time.time()
                    new_state = GameState.deserialize(data)
                    
                    time_diff = receive_time - new_state.timestamp
                    
                    self.game_state.ball.x = new_state.ball.x
                    self.game_state.ball.y = new_state.ball.y
                    self.game_state.ball.vx = new_state.ball.vx
                    self.game_state.ball.vy = new_state.ball.vy
                    if self.protocol == 'UDP' and time_diff > 0:
                        self.game_state.extrapolate_ball(time_diff)
                        self.metrics['position_extrapolations'].append(time_diff)
                    else:
                        self.metrics['position_interpolations'].append(time_diff)
                    
                    self.game_state.paddle1 = new_state.paddle1
                    self.game_state.paddle2 = new_state.paddle2
                    self.game_state.score1 = new_state.score1
                    self.game_state.score2 = new_state.score2
                    
                    self.metrics['latencies'].append(time_diff * 1000)
                    if len(self.metrics['latencies']) > 100:
                        self.metrics['latencies'].pop(0)
            except:
                pass

    def render(self):
        while self.running:
            with self.lock:
                self.ball_sprite.goto(self.game_state.ball.x - 400, 300 - self.game_state.ball.y)
                
                self.paddle_l.goto(self.game_state.paddle1.x - 400, 300 - (self.game_state.paddle1.y + self.game_state.paddle1.height / 2))
                self.paddle_r.goto(self.game_state.paddle2.x - 400, 300 - (self.game_state.paddle2.y + self.game_state.paddle2.height / 2))
                
                self.score_display.clear()
                self.score_display.write(f"{self.game_state.score1}  :  {self.game_state.score2}", align="center", font=("Arial", 32, "normal"))
                
                if self.metrics['latencies']:
                    avg_latency = sum(self.metrics['latencies']) / len(self.metrics['latencies'])
                    protocol_info = f"{self.protocol} | Latency: {avg_latency:.2f}ms"
                    
                    if self.protocol == 'UDP' and self.metrics['position_extrapolations']:
                        avg_extrap = sum(self.metrics['position_extrapolations']) / len(self.metrics['position_extrapolations'])
                        protocol_info += f" | Extrapolation: {avg_extrap*1000:.2f}ms"
                    
                    self.metrics_display.clear()
                    self.metrics_display.write(protocol_info, font=("Arial", 10, "normal"))
            
            self.screen.update()
            time.sleep(1/60)

    def start(self):
        self.connect()
        
        input_thread = threading.Thread(target=self.send_input, daemon=True)
        receive_thread = threading.Thread(target=self.receive_state, daemon=True)
        render_thread = threading.Thread(target=self.render, daemon=True)
        
        input_thread.start()
        receive_thread.start()
        render_thread.start()
        
        try:
            self.screen.mainloop()
        except KeyboardInterrupt:
            self.running = False
            if self.socket:
                self.socket.close()


if __name__ == '__main__':
    protocol = sys.argv[1] if len(sys.argv) > 1 else 'TCP'
    player_id = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    
    client = GameClient('localhost', player_id, protocol)
    client.start()
