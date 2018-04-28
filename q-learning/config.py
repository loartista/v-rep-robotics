#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import numpy as np

n_episodes = 6000
restore = True
alpha = 0.99
gamma = 0.9
epsilon = 0.3
valid_actions = ['forward', 'left_forward', 'right_forward']
SPEED = 3

wait_response = False
ultra_distribution = ['left_ultra', 'right_ultra']
n_ultra = len(ultra_distribution)
valid_actions_dict = {valid_actions[0]: np.array([SPEED, SPEED]),
                      valid_actions[1]: np.array([0, SPEED]),
                      valid_actions[2]: np.array([SPEED, 0])}
tolerance = 0.05
time_step = 0.05
grid_width = 0.002
