#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

import unittest
import sys


if __name__ == '__main__':
    loader = unittest.TestLoader()
    tests = loader.discover('tests')
    testRunner = unittest.runner.TextTestRunner(stream=sys.stdout, verbosity=2)
    runner = testRunner.run(tests)
    sys.exit(int(bool(runner.failures or result.errors)))
