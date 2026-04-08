import struct
import time
import math

class Ball:
    def __init__(self, x=400, y=300, vx=5, vy=5, radius=5):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.radius = radius

    def update(self, width=800, height=600):
        self.x += self.vx
        self.y += self.vy

        if self.y - self.radius <= 0 or self.y + self.radius >= height:
            self.vy *= -1
            self.y = max(self.radius, min(height - self.radius, self.y))

        if self.x < 0 or self.x > width:
            return True
        return False

    def serialize(self):
        return struct.pack('!fffff', self.x, self.y, self.vx, self.vy, self.radius)

    @staticmethod
    def deserialize(data):
        x, y, vx, vy, radius = struct.unpack('!fffff', data)
        ball = Ball(x, y, vx, vy, radius)
        return ball


class Paddle:
    def __init__(self, x, y, width=15, height=100):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.vy = 0
        self.speed = 8

    def update(self, height=600):
        self.y += self.vy
        self.y = max(0, min(height - self.height, self.y))

    def move_up(self):
        self.vy = -self.speed

    def move_down(self):
        self.vy = self.speed

    def stop(self):
        self.vy = 0

    def serialize(self):
        return struct.pack('!ffff', self.x, self.y, self.width, self.height)

    @staticmethod
    def deserialize(data):
        x, y, width, height = struct.unpack('!ffff', data)
        paddle = Paddle(x, y, width, height)
        return paddle


class GameState:
    def __init__(self):
        self.ball = Ball()
        self.paddle1 = Paddle(20, 250)
        self.paddle2 = Paddle(765, 250)
        self.score1 = 0
        self.score2 = 0
        self.timestamp = time.time()
        self.width = 800
        self.height = 600
        self.ball_history = []

    def check_paddle_collision(self, paddle):
        if (self.ball.x - self.ball.radius <= paddle.x + paddle.width and
            self.ball.x + self.ball.radius >= paddle.x and
            self.ball.y >= paddle.y and
            self.ball.y <= paddle.y + paddle.height):
            
            self.ball.vx *= -1.05
            self.ball.x = paddle.x + paddle.width + self.ball.radius if paddle == self.paddle1 else paddle.x - self.ball.radius
            
            hit_pos = (self.ball.y - paddle.y) / paddle.height
            max_angle = math.pi / 4
            angle = (hit_pos - 0.5) * max_angle * 2
            speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
            self.ball.vx = speed * math.cos(angle) * (1 if paddle == self.paddle1 else -1)
            self.ball.vy = speed * math.sin(angle)
            return True
        return False

    def update(self):
        self.ball.update(self.width, self.height)
        self.check_paddle_collision(self.paddle1)
        self.check_paddle_collision(self.paddle2)

        if self.ball.x < 0:
            self.score2 += 1
            self.reset_ball()
        elif self.ball.x > self.width:
            self.score1 += 1
            self.reset_ball()

        self.paddle1.update(self.height)
        self.paddle2.update(self.height)
        self.timestamp = time.time()

        self.ball_history.append((self.ball.x, self.ball.y, time.time()))
        if len(self.ball_history) > 100:
            self.ball_history.pop(0)

    def reset_ball(self):
        self.ball = Ball(400, 300, 5 if self.score1 > self.score2 else -5, 5)

    def serialize(self):
        data = struct.pack('!ii', self.score1, self.score2)
        data += self.ball.serialize()
        data += self.paddle1.serialize()
        data += self.paddle2.serialize()
        data += struct.pack('!d', self.timestamp)
        return data

    @staticmethod
    def deserialize(data):
        state = GameState()
        offset = 0
        state.score1, state.score2 = struct.unpack('!ii', data[offset:offset+8])
        offset += 8
        state.ball = Ball.deserialize(data[offset:offset+20])
        offset += 20
        state.paddle1 = Paddle.deserialize(data[offset:offset+16])
        offset += 16
        state.paddle2 = Paddle.deserialize(data[offset:offset+16])
        offset += 16
        state.timestamp = struct.unpack('!d', data[offset:offset+8])[0]
        return state

    def interpolate_ball(self, other_state, alpha):
        if alpha < 0:
            alpha = 0
        elif alpha > 1:
            alpha = 1
        self.ball.x += (other_state.ball.x - self.ball.x) * alpha
        self.ball.y += (other_state.ball.y - self.ball.y) * alpha

    def extrapolate_ball(self, time_delta):
        self.ball.x += self.ball.vx * time_delta
        self.ball.y += self.ball.vy * time_delta
