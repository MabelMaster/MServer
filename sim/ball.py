import math
from dataclasses import dataclass

class Arena:
    def __init__(self, width, height):
        self.width=width
        self.height=height

class Ball:
    def __init__(self, x, y, vx, vy, radius,width,height):
        values = (x, y, vx, vy, radius, width, height)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("coordinates must be finite")
        if radius <= 0 or width <= 2 * radius or height <= 2 * radius:
            raise ValueError("field must be larger than the ball")
        if not (radius <= x <= width - radius and radius <= y <= height - radius):
            raise ValueError("center starts outside the field")
        self.x=x
        self.y=y
        self.vx=vx
        self.vy=vy
        self.radius=radius
        self.arena=Arena(width,height)
    def position(self):
        return self.x, self.y
    def velocity(self):
        return self.vx, self.vy
    def move(self,dt):
        x,vx=reflect(self.x+self.vx*dt,self.vx,self.radius, self.arena.width-self.radius)
        y,vy=reflect(self.y+self.vy*dt,self.vy,self.radius,self.arena.height-self.radius)
        self.x,self.vx,self.y,self.vy=x,vx,y,vy

def reflect(pos,vel,low,high):
    if pos < low:
        pos=low+(low-pos)
        vel=-vel
    elif pos > high:
        pos=high-(pos-high)
        vel=-vel
    if pos < low or pos > high:
        raise ValueError(f"Position {pos} is out of bounds")
    return pos,vel



