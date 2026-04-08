import pygame
import socket
import struct
import threading
import time
import sys
from game import GameState

class PingPongGUI:
    def __init__(self, server_host='localhost', player_id=0, protocol='TCP'):
        pygame.init()
        
        self.width = 1000
        self.height = 700
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(f"Ping Pong - {protocol} - Player {player_id}")
        
        self.clock = pygame.time.Clock()
        self.running = True
        self.font_large = pygame.font.Font(None, 80)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        
        self.server_host = server_host
        self.player_id = player_id
        self.protocol = protocol.upper()
        self.server_port_tcp = 35000
        self.server_port_udp = 35001
        
        self.game_state = GameState()
        self.socket = None
        self.lock = threading.Lock()
        
        self.keys_pressed = {'up': False, 'down': False}
        self.last_sent = time.time()
        self.send_rate = 1/60
        
        self.metrics = {
            'latencies': [],
            'position_jumps': []
        }
        
        self.game_width = 800
        self.game_height = 600
        self.offset_x = (self.width - self.game_width) // 2
        self.offset_y = (self.height - self.game_height) // 2

    def connect(self):
        if self.protocol == 'TCP':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port_tcp))
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.keys_pressed['up'] = True
                elif event.key == pygame.K_DOWN:
                    self.keys_pressed['down'] = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_UP:
                    self.keys_pressed['up'] = False
                elif event.key == pygame.K_DOWN:
                    self.keys_pressed['down'] = False

    def send_input(self):
        while self.running:
            current_time = time.time()
            if current_time - self.last_sent >= self.send_rate:
                with self.lock:
                    command = 'S'
                    if self.keys_pressed['up']:
                        command = 'U'
                    elif self.keys_pressed['down']:
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
                    
                    old_pos = (self.game_state.ball.x, self.game_state.ball.y)
                    
                    time_diff = receive_time - new_state.timestamp
                    
                    if self.protocol == 'UDP' and time_diff > 0:
                        self.game_state.ball.x = new_state.ball.x
                        self.game_state.ball.y = new_state.ball.y
                        self.game_state.ball.vx = new_state.ball.vx
                        self.game_state.ball.vy = new_state.ball.vy
                        self.game_state.extrapolate_ball(time_diff)
                    else:
                        alpha = min(0.1, time_diff)
                        self.game_state.interpolate_ball(new_state, alpha)
                    
                    new_pos = (self.game_state.ball.x, self.game_state.ball.y)
                    jump = ((new_pos[0] - old_pos[0])**2 + (new_pos[1] - old_pos[1])**2)**0.5
                    
                    if jump > 20:
                        self.metrics['position_jumps'].append(jump)
                        if len(self.metrics['position_jumps']) > 100:
                            self.metrics['position_jumps'].pop(0)
                    
                    self.game_state.paddle1 = new_state.paddle1
                    self.game_state.paddle2 = new_state.paddle2
                    self.game_state.score1 = new_state.score1
                    self.game_state.score2 = new_state.score2
                    
                    self.metrics['latencies'].append(time_diff * 1000)
                    if len(self.metrics['latencies']) > 100:
                        self.metrics['latencies'].pop(0)
            except:
                pass

    def draw(self):
        self.screen.fill((20, 20, 30))
        
        pygame.draw.rect(self.screen, (50, 50, 70), (self.offset_x, self.offset_y, self.game_width, self.game_height))
        
        for y in range(self.offset_y, self.offset_y + self.game_height, 20):
            pygame.draw.line(self.screen, (100, 100, 120), 
                           (self.offset_x + self.game_width // 2, y),
                           (self.offset_x + self.game_width // 2, y + 10), 2)
        
        with self.lock:
            ball_x = self.offset_x + self.game_state.ball.x
            ball_y = self.offset_y + self.game_state.ball.y
            pygame.draw.circle(self.screen, (255, 100, 100), (int(ball_x), int(ball_y)), int(self.game_state.ball.radius))
            
            paddle1_x = self.offset_x + self.game_state.paddle1.x
            paddle1_y = self.offset_y + self.game_state.paddle1.y
            pygame.draw.rect(self.screen, (100, 200, 255), 
                           (paddle1_x, paddle1_y, self.game_state.paddle1.width, self.game_state.paddle1.height))
            
            paddle2_x = self.offset_x + self.game_state.paddle2.x
            paddle2_y = self.offset_y + self.game_state.paddle2.y
            pygame.draw.rect(self.screen, (100, 255, 100), 
                           (paddle2_x, paddle2_y, self.game_state.paddle2.width, self.game_state.paddle2.height))
            
            score_text = self.font_large.render(f"{self.game_state.score1}  :  {self.game_state.score2}", 
                                               True, (255, 255, 255))
            score_rect = score_text.get_rect(center=(self.width // 2, self.offset_y - 30))
            self.screen.blit(score_text, score_rect)
            
            if self.metrics['latencies']:
                avg_latency = sum(self.metrics['latencies']) / len(self.metrics['latencies'])
                protocol_text = f"{self.protocol} | Latência: {avg_latency:.1f}ms"
                
                if self.protocol == 'UDP' and self.metrics['position_jumps']:
                    avg_jump = sum(self.metrics['position_jumps']) / len(self.metrics['position_jumps'])
                    protocol_text += f" | Salto: {avg_jump:.1f}px"
                
                info_surface = self.font_small.render(protocol_text, True, (255, 255, 100))
                self.screen.blit(info_surface, (20, 20))
            
            if self.protocol == 'TCP':
                status = "TCP (Confiável)"
                color = (100, 200, 255)
            else:
                status = "UDP (Rápido)"
                color = (100, 255, 100)
            
            status_text = self.font_small.render(status, True, color)
            self.screen.blit(status_text, (self.width - 200, 20))
            
            controls_text = self.font_small.render("↑ Cima | ↓ Baixo", True, (200, 200, 200))
            self.screen.blit(controls_text, (self.width // 2 - 100, self.height - 30))
        
        pygame.display.flip()

    def run(self):
        self.connect()
        
        input_thread = threading.Thread(target=self.send_input, daemon=True)
        receive_thread = threading.Thread(target=self.receive_state, daemon=True)
        
        input_thread.start()
        receive_thread.start()
        
        try:
            while self.running:
                self.handle_input()
                self.draw()
                self.clock.tick(60)
        except KeyboardInterrupt:
            self.running = False
        finally:
            if self.socket:
                self.socket.close()
            pygame.quit()


if __name__ == '__main__':
    server_host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    protocol = sys.argv[2] if len(sys.argv) > 2 else 'TCP'
    player_id = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    gui = PingPongGUI(server_host, player_id, protocol)
    gui.run()
