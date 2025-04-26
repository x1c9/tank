#!/usr/bin/env python3

import threading
import rospy
from geometry_msgs.msg import Twist
import sys
from select import select
import termios
import tty

msg = """
Dieu khien xe:
w - tien
s - lui
a - quay trai
d - quay phai
f - thoat chuong trinh
"""

moveBindings = {
    'w': (0, 1),
    's': (0, -1),
    'a': (1, 0),
    'd': (-1, 0)
}

class PublishThread(threading.Thread):
    def __init__(self, rate):
        super(PublishThread, self).__init__()
        self.pub_base = rospy.Publisher('/diff_drive_controller/cmd_vel', Twist, queue_size=10)
        self.x = 0.0
        self.th = 0.0
        self.speed = 0.0
        self.turn = 0.0
        self.condition = threading.Condition()
        self.done = False
        self.timeout = 1.0 / rate if rate != 0.0 else 0.1
        self.start()

    def update(self, x, th, speed, turn):
        self.condition.acquire()
        self.x = x
        self.th = th
        self.speed = speed
        self.turn = turn
        self.condition.notify()
        self.condition.release()

    def stop(self):
        self.done = True
        self.update(0, 0, 0, 0)
        self.join()

    def run(self):
        twist = Twist()
        while not self.done:
            self.condition.acquire()
            self.condition.wait(self.timeout)
            twist.linear.x = self.x * self.speed
            twist.angular.z = self.th * self.turn
            self.condition.release()
            self.pub_base.publish(twist)
        twist.linear.x = 0
        twist.angular.z = 0
        self.pub_base.publish(twist)

def getKey(settings, timeout):
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select([sys.stdin], [], [], timeout)
    key = sys.stdin.read(1) if rlist else ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def saveTerminalSettings():
    return termios.tcgetattr(sys.stdin)

def restoreTerminalSettings(old_settings):
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    settings = saveTerminalSettings()
    rospy.init_node('keyboard_control')

    speed = rospy.get_param("~speed", 10.0)
    turn = rospy.get_param("~turn", 10.0)
    repeat = rospy.get_param("~repeat_rate", 0.0)
    key_timeout = rospy.get_param("~key_timeout", 0.5)

    pub_thread = PublishThread(repeat)
    x = 0
    th = 0

    try:
        pub_thread.update(x, th, speed, turn)
        print(msg)

        while not rospy.is_shutdown():
            key = getKey(settings, key_timeout)
            old_x, old_th = x, th
            if key in moveBindings:
                x = moveBindings[key][0]
                th = moveBindings[key][1]
            elif key == 'f' or key == '\x03':
                break
            else:
                x = 0
                th = 0
            if old_x != x or old_th != th:
                pub_thread.update(x, th, speed, turn)

    except Exception as e:
        rospy.logerr(f"Error occurred: {e}")

    finally:
        pub_thread.stop()
        restoreTerminalSettings(settings)