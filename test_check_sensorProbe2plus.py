#!/usr/bin/env python3

import unittest
import unittest.mock as mock
import sys

sys.path.append('..')

from check_sensorProbe2plus import convert_state_to_nagios
from check_sensorProbe2plus import print_status_message

from check_sensorProbe2plus import NagiosState

class UtilTesting(unittest.TestCase):

    def test_state(self):
        actual = convert_state_to_nagios(1)
        expected = NagiosState.UNKNOWN

        self.assertEqual(actual, expected)

    @mock.patch('builtins.print')
    def test_status_message(self, mock_print):
        sensor_states = {
            "OK": [],
            "WARNING": [],
            "CRITICAL": [],
            "UNKNOWN": [],
        }

        print_status_message(sensor_states, "perfdata")

        calls = [mock.call('OK sensorProbe2plus: Sensor reports that everything is fine|p e r f d a t a ')]

        mock_print.assert_has_calls(calls)

