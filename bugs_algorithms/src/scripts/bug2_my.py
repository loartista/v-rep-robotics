#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'ar1'

import math
import time
import vrep
import sys
import numpy as np

from support import *

PI = math.pi

class State:
    MOVING = 1
    ROTATING = 2
    ROUNDING = 3

class Bug2:
    def __init__(self):

        self.state = State.MOVING

        self.MIN_DETECTION_DIST = 0.0
        self.MAX_DETECTION_DIST = 1.0

        self.TARGET_NAME = 'target'
        self.BOT_NAME = 'Bot'
        self.WHEEL_SPEED = 1.0
        self.INDENT_DIST = 0.5

        self.SLEEP_TIME = 0.2

        self.bot_pos = None
        self.bot_euler_angles = None
        self.target_pos = None
        self.obstacle_dist_stab_PID = None
        self.obstacle_follower_PID = None

        self.targetDir = None
        self.botDir = None
        self.botPos = None
        self.targetPos = None
        self.botEulerAngles = None

        self.start_target_pos = None
        self.start_bot_pos = None

        self.detect = np.zeros(16)

        self._init_client_id()
        self._init_handles()
        self._init_sensor_handles()


    def _init_client_id(self):
        vrep.simxFinish(-1)

        self.client_id = vrep.simxStart('127.0.0.1', 19999, True, True, 5000, 5)

        if self.client_id != -1:
            print 'Connected to remote API server'

        else:
            print 'Connection not successful'
            sys.exit('Could not connect')

    @staticmethod
    def angle_between_vectors(a, b):  # a -> b

        a = a.unitVector()
        b = b.unitVector()
        angle = math.acos(b.dot(a))
        if (a.multiply(b)).z > 0.0:
            return -angle
        return angle

    def _init_handles(self):

        self._init_wheels_handle()

        self._init_target_handle()

        self._init_robot_handle()

    def _init_robot_handle(self):
        # handle of robot
        error_code, self.bot_handle = vrep.simxGetObjectHandle(self.client_id, self.BOT_NAME,
                                                               vrep.simx_opmode_oneshot_wait)

    def _init_target_handle(self):
        # get handle of target robot
        error_code, self.target_handle = vrep.simxGetObjectHandle(self.client_id, self.TARGET_NAME,
                                                                  vrep.simx_opmode_oneshot_wait)

    def _init_wheels_handle(self):
        # get handles of robot wheels
        error_code, self.left_motor_handle = vrep.simxGetObjectHandle(self.client_id, 'Pioneer_p3dx_leftMotor',
                                                                     vrep.simx_opmode_oneshot_wait)
        error_code, self.right_motor_handle = vrep.simxGetObjectHandle(self.client_id, 'Pioneer_p3dx_rightMotor',
                                                                      vrep.simx_opmode_oneshot_wait)

    def _init_sensor_handles(self):

        self.sensor_handles = []  # empty list for handles

        for x in range(1, 16 + 1):
            error_code, sensor_handle = vrep.simxGetObjectHandle(self.client_id, 'Pioneer_p3dx_ultrasonicSensor' + str(x),
                                                                 vrep.simx_opmode_oneshot_wait)
            self.sensor_handles.append(sensor_handle)
            vrep.simxReadProximitySensor(self.client_id, sensor_handle, vrep.simx_opmode_streaming)

    def _init_values(self):

        error_code, self.target_pos = vrep.simxGetObjectPosition(self.client_id, self.target_handle, -1,
                                                                 vrep.simx_opmode_oneshot)

        error_code, self.bot_pos = vrep.simxGetObjectPosition(self.client_id, self.bot_handle, -1,
                                                              vrep.simx_opmode_oneshot)

        error_code, self.bot_euler_angles = vrep.simxGetObjectOrientation(self.client_id, self.bot_handle, -1,
                                                                          vrep.simx_opmode_streaming)

    def read_values(self):

        error_code, self.target_pos = vrep.simxGetObjectPosition(self.client_id, self.target_handle, -1,
                                                                 vrep.simx_opmode_streaming)

        error_code, self.bot_pos = vrep.simxGetObjectPosition(self.client_id, self.bot_handle, -1,
                                                              vrep.simx_opmode_streaming)

        error_code, self.bot_euler_angles = vrep.simxGetObjectOrientation(self.client_id, self.bot_handle, -1,
                                                                          vrep.simx_opmode_streaming)

    def stop_move(self):
        error_code = vrep.simxSetJointTargetVelocity(self.client_id, self.left_motor_handle,  0, vrep.simx_opmode_streaming)
        error_code = vrep.simxSetJointTargetVelocity(self.client_id, self.right_motor_handle, 0, vrep.simx_opmode_streaming)

    def read_from_sensors(self):

        for i in range(0, 16):

            error_code, detection_state, detected_point, detected_object_handle, detected_surface_normal_vector = vrep.simxReadProximitySensor(self.client_id, self.sensor_handles[i], vrep.simx_opmode_streaming)

            dist = math.sqrt(np.sum(np.array(detected_point) ** 2))

            if dist < self.MIN_DETECTION_DIST:
                self.detect[i] = 0.0
            elif dist > self.MAX_DETECTION_DIST or detection_state is False:
                self.detect[i] = 1.0
            else:
                self.detect[i] = 1.0 - ((dist - self.MAX_DETECTION_DIST) / (self.MIN_DETECTION_DIST - self.MAX_DETECTION_DIST))

    def loop(self):

        self._init_values()

        self.obstacle_dist_stab_PID = PIDController(50.0)
        self.obstacle_follower_PID = PIDController(50.0)
        self.obstacle_dist_stab_PID.setCoefficients(2, 0, 0.5)
        self.obstacle_follower_PID.setCoefficients(2, 0, 0)

        self.targetDir = np.zeros(3)

        while True:

            self.tick()

            self.stop_move()
            self.read_values()

            self.targetPos = Vector3(x=self.target_pos[0], y=self.target_pos[1], z=self.target_pos[2])

            self.botPos = Vector3(x=self.bot_pos[0], y=self.bot_pos[1], z=self.bot_pos[2])

            self.botEulerAngles = Vector3(x=self.bot_euler_angles[0], y=self.bot_euler_angles[1], z=self.bot_euler_angles[2])

            if self.start_bot_pos is None:
                self.start_bot_pos = self.botPos
            if self.start_target_pos is None:
                self.start_target_pos = self.targetPos

            self.read_from_sensors()

            self.targetPos.z = self.botPos.z = 0.0
            qRot = Quaternion()
            qRot.set_from_vector(self.botEulerAngles.z, Vector3(0.0, 0.0, 1.0))
            self.botDir = qRot.rotate(Vector3(1.0, 0.0, 0.0))

            if self.state == State.MOVING:
                self.action_moving()
            elif self.state == State.ROTATING:
                self.action_rotating()
            elif self.state == State.ROUNDING:
                self.action_rounding()

    def action_moving(self):

        if self.detect[4] < 0.6:

            self.state = State.ROTATING
            tmp = Quaternion()
            tmp.set_from_vector(PI / 2.0, Vector3(0.0, 0.0, 1.0))
            self.targetDir = tmp.rotate(self.botDir)

            return

        angle = self.angle_between_vectors(self.botDir, self.targetPos.minus(self.botPos))

        if math.fabs(angle) > 1.0 / 180.0 * PI:
            vrep.simxSetJointTargetVelocity(self.client_id, self.left_motor_handle,  self.WHEEL_SPEED + angle, vrep.simx_opmode_streaming)
            vrep.simxSetJointTargetVelocity(self.client_id, self.right_motor_handle, self.WHEEL_SPEED - angle, vrep.simx_opmode_streaming)
        else:
            vrep.simxSetJointTargetVelocity(self.client_id, self.left_motor_handle,  self.WHEEL_SPEED, vrep.simx_opmode_streaming)
            vrep.simxSetJointTargetVelocity(self.client_id, self.right_motor_handle, self.WHEEL_SPEED, vrep.simx_opmode_streaming)

    def action_rotating(self):

        angle = self.angle_between_vectors(self.botDir, self.targetDir)

        if math.fabs(angle) > 5.0 / 180.0 * PI:
            vrep.simxSetJointTargetVelocity(self.client_id, self.left_motor_handle,   angle, vrep.simx_opmode_streaming)
            vrep.simxSetJointTargetVelocity(self.client_id, self.right_motor_handle, -angle, vrep.simx_opmode_streaming)
        else:
            self.state = State.ROUNDING

    def action_rounding(self):

        if self.is_bot_on_the_constant_direction():
            self.state = State.MOVING
            return

        delta = self.detect[7] - self.detect[8]

        if delta < 0.0:
            obstacle_dist = self.detect[7] - self.INDENT_DIST
        else:
            obstacle_dist = self.detect[8] - self.INDENT_DIST

        u_obstacle_dist_stab = self.obstacle_dist_stab_PID.output(obstacle_dist)
        u_obstacle_follower = self.obstacle_follower_PID.output(delta)

        vrep.simxSetJointTargetVelocity(self.client_id, self.left_motor_handle,  self.WHEEL_SPEED + u_obstacle_follower + u_obstacle_dist_stab - (1 - self.detect[4]), vrep.simx_opmode_streaming)
        vrep.simxSetJointTargetVelocity(self.client_id, self.right_motor_handle, self.WHEEL_SPEED - u_obstacle_follower - u_obstacle_dist_stab + (1 - self.detect[4]), vrep.simx_opmode_streaming)

    def tick(self):
        time.sleep(self.SLEEP_TIME)

    def distance_between(self, botPos, targetPost):
        return math.sqrt((botPos.x - targetPost.x) ** 2 + (botPos.y - targetPost.y) ** 2)

    def is_bot_on_the_constant_direction(self):
        # (x-x1)/(x2-x1) = (y-y1)/(y2-y1).
        diff_x = (self.botPos.x - self.start_bot_pos.x) / (self.start_target_pos.x - self.start_bot_pos.x)
        diff_y = (self.botPos.y - self.start_bot_pos.y) / (self.start_target_pos.y - self.start_bot_pos.y)
        delta = 0.01
        if diff_x - delta < diff_y < diff_x + delta:
            return True
        return False

####################################################

if __name__ == '__main__':

    bug2 = Bug2()

    bug2.loop()




